#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

#    callirhoe - high quality calendar rendering
#    Copyright (C) 2012-2014 George M. Tzoumas

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see http://www.gnu.org/licenses/

"""high quality calendar rendering"""

# TODO:

# fix auto-measure rendering (cairo)
# fix plugin loading (without global vars)
# week markers selectable
# test layouts

# allow to change background color (fill), other than white
# page spec parse errors
# mobile themes (e.g. 800x480)
# photo support (like ImageMagick's polaroid effect)
# .callirhoe/config : default values for plugins (styles/layouts/lang...) and cmdline

# MAYBE-TODO:
# implement various data sources
# auto-landscape? should aim for matrix or bars?
# allow /usr/bin/date-like formatting %x... 
# improve file matching with __init__ when lang known
# styles and geometries could be merged, css-like
#  then we can apply a chain of --style a --style b ...
#  and b inherits from a and so on
#  however, this would require dynamically creating a class that inherits from others...

# CANNOT UPGRADE TO argparse !!! -- how to handle [[month] year] form?

_version = "0.4.0"

import calendar
import sys
import time
import optparse
import lib.xcairo as xcairo
import lib.holiday as holiday

from lib.plugin import *
# TODO: SEE IF IT CAN BE MOVED INTO lib.plugin ...
def import_plugin(plugin_paths, cat, longcat, longcat2, listopt, preset):
    """import a plugin making it visible

    I{Example:}

    >>> Language = import_plugin(get_plugin_paths(), "lang", "language", "languages", "--list-languages", "EN")

    @param plugin_paths: list of plugin search paths
    @param cat: short category name (for folder name)
    @param longcat: long category name
    @param longcat2: long category name in plural form
    @param listopt: option name
    @param preset: default value

    @note: Aimed for internal use with I{lang}, I{style}, I{geom}, I{layouts}.
    """
    try:
        found = available_files(plugin_paths[0], cat, preset) + available_files(plugin_paths[1], cat, preset)
        if len(found) == 0: raise IOError
        old = sys.path[0];
        sys.path[0] = found[0][1]
        m = __import__("%s.%s" % (cat,preset), globals(), locals(), [ "*" ])
        sys.path[0] = old
        return m
    except IOError:
        sys.exit("callirhoe: %s definition '%s' not found, use %s to see available definitions" % (longcat,
                               preset,listopt))
    except ImportError:
        sys.exit("callirhoe: error loading %s definition '%s'" % (longcat, preset))

def print_examples():
    """print usage examples"""
    print """Examples:

Create a calendar of the current year (by default in a 4x3 grid):
    $ callirhoe my_calendar.pdf 

Same as above, but in landscape mode (3x4) (for printing):
    $ callirhoe --landscape my_calendar.pdf 

Landscape via rotation (for screen):
    $ callirhoe --paper=a4w --rows=3 my_calendar.pdf

Let's try with bars instead of boxes:
    $ callirhoe -t bars my_calendar.pdf

In landscape mode, one row only looks quite good:
    $ callirhoe -t bars --landscape --rows=1 my_calendar.pdf

How about a more flat look?
    $ callirhoe -t sparse -s bw_sparse --rows=1 --cols=3 my_calendar.pdf

Calendar of 24 consecutive months, starting from current month:
    $ callirhoe 0:24 0 my_calendar.pdf
    
Create a 600-dpi PNG file so that we can edit it with some effects in order to print an A3 poster:
    $ callirhoe my_poster.png --paper=a3 --dpi=600 --opaque

Create a calendar as a full-hd wallpaper (1920x1080):
    $ callirhoe wallpaper.png --paper=-1920:-1080 --opaque --rows=3 --no-shadow -s rainbow-gfs
and do some magic with ImageMagick! ;)
    $ convert wallpaper.png -negate fancy.png
    
"""

def add_list_option(parser, opt):
    """add a --list-I{plugins} option to parser

    @note: To be used with I{languages}, I{layouts}, I{styles} and I{geometries}.
    """
    parser.add_option("--list-%s" % opt, action="store_true", dest="list_%s" % opt, default=False,
                       help="list available %s" % opt)

def itoa(s, lower_bound=None, upper_bound=None, prefix=''):
    """convert integer to string, exiting on error (for cmdline parsing)

    @param lower_bound: perform additional check so that value >= I{lower_bound}
    @param upper_bound: perform additional check so that value <= I{upper_bound}
    @param prefix: output prefix for error reporting
    """
    try:
        k = int(s);
        if lower_bound is not None:
            if k < lower_bound:
                sys.exit(prefix + "value '" + s +"' out of range: should not be less than %d" % lower_bound)
        if upper_bound is not None:
            if k > upper_bound:
                sys.exit(prefix + "value '" + s +"' out of range: should not be greater than %d" % upper_bound)
    except ValueError as e:
        sys.exit(prefix + "invalid integer value '" + s +"'")
    return k

def _parse_month(mstr):
    """get a month value (0-12) from I{mstr}, exiting on error (for cmdline parsing)"""
    m = itoa(mstr,lower_bound=0,upper_bound=12,prefix='month: ')
    if m == 0: m = time.localtime()[1]
    return m

def parse_month_range(s):
    """return (Month,Span) by parsing range I{Month}, I{Month1}-I{Month2} or I{Month}:I{Span}"""
    if ':' in s:
        t = s.split(':')
        if len(t) != 2: sys.exit("invalid month range '" + s + "'")
        Month = _parse_month(t[0])
        MonthSpan = itoa(t[1],lower_bound=0,prefix='month span: ')
    elif '-' in s:
        t = s.split('-')
        if len(t) != 2: sys.exit("invalid month range '" + s + "'")
        Month = _parse_month(t[0])
        MonthSpan = itoa(t[1],lower_bound=Month+1,prefix='month range: ') - Month + 1
    else:
        Month = _parse_month(s)
        MonthSpan = 1
    return (Month,MonthSpan)

def parse_year(ystr):
    """get a year value (>=0) from I{ystr}, exiting on error (for cmdline parsing)"""
    y = itoa(ystr,lower_bound=0,prefix='year: ')
    if y == 0: y = time.localtime()[0]
    return y

def extract_parser_args(arglist, parser, pos = -1):
    """extract options belonging to I{parser} along with I{pos} positional arguments

    @param arglist: argument list to extract
    @param parser: parser object to be used for extracting
    @param pos: number of positional options to be extracted

    if I{pos}<0 then all positional arguments are extracted, otherwise,
    only I{pos} arguments are extracted. arglist[0] (usually sys.argv[0]) is also positional
    argument!
    @return: tuple (argv1,argv2) with extracted argument list and remaining argument list
    """
    argv = [[],[]]
    posc = 0
    push_value = None
    for x in arglist:
        if push_value:
            push_value.append(x)
            push_value = None
            continue
        # get option name (long options stop at '=')
        y = x[0:x.find('=')] if '=' in x else x
        if x[0] == '-':
            if parser.has_option(y):
                argv[0].append(x)
                if not x.startswith('--') and parser.get_option(y).takes_value():
                    push_value = argv[0]
            else:
                argv[1].append(x)
        else:
            if pos < 0:
                argv[0].append(x)
            else:
                argv[posc >= pos].append(x)
                posc += 1
    return tuple(argv)

def get_parser():
    """get the argument parser object"""
    parser = optparse.OptionParser(usage="usage: %prog [options] [[MONTH[-MONTH2|:SPAN]] YEAR] FILE",
           description="High quality calendar rendering with vector graphics. "
           "By default, a calendar of the current year in pdf format is written to FILE. "
           "Alternatively, you can select a specific YEAR (0=current), "
           "and a month range from MONTH (0-12, 0=current) to MONTH2 or for SPAN months.",
           version="callirhoe " + _version)
    parser.add_option("-l", "--lang",  dest="lang", default="EN",
                    help="choose language [%default]")
    parser.add_option("-t", "--layout",  dest="layout", default="classic",
                    help="choose layout [%default]")
    parser.add_option("-?", "--layout-help",  dest="layouthelp", action="store_true", default=False,
                    help="show layout-specific help")
    parser.add_option("--examples", dest="examples", action="store_true",
                    help="display some usage examples")
    parser.add_option("-s", "--style",  dest="style", default="default",
                    help="choose style [%default]")
    parser.add_option("-g", "--geometry",  dest="geom", default="default",
                    help="choose geometry [%default]")
    parser.add_option("--landscape", action="store_true", dest="landscape", default=False,
                    help="landscape mode")
    parser.add_option("--dpi", type="float", default=72.0,
                    help="set DPI (for raster output) [%default]")
    parser.add_option("--paper", default="a4",
                    help="set paper type; PAPER can be an ISO paper type (a0..a9 or a0w..a9w) or of the "
                    "form W:H; positive values correspond to W or H mm, negative values correspond to "
                    "-W or -H pixels; 'w' suffix swaps width & height [%default]")
    parser.add_option("--border", type="float", default=3,
                    help="set border size (in mm) [%default]")
    parser.add_option("-H", "--with-holidays", action="append", dest="holidays",
                    help="load holiday file (can be used multiple times)")
    parser.add_option("--short-monthnames", action="store_true", default=False,
                      help="user the short version of month names (defined in language file) [%default]")
    parser.add_option("--long-daynames", action="store_true", default=False,
                    help="user the long version of day names (defined in language file) [%default]")
    parser.add_option("-T", "--terse-holidays", action="store_false", dest="multiday_holidays",
                    default=True, help="do not print holiday end markers and omit dots")

    for x in ["languages", "layouts", "styles", "geometries"]:
        add_list_option(parser, x)

    parser.add_option("--lang-var", action="append", dest="lang_assign",
                    help="modify a language variable")
    parser.add_option("--style-var", action="append", dest="style_assign",
                    help="modify a style variable, e.g. dom.frame_thickness=0")
    parser.add_option("--geom-var", action="append", dest="geom_assign",
                    help="modify a geometry variable")
    return parser

if __name__ == "__main__":
    parser = get_parser()

    sys.argv,argv2 = extract_parser_args(sys.argv,parser)
    (options,args) = parser.parse_args()

    list_and_exit = False
    if options.list_languages:
        for x in plugin_list("lang"): print x[0],
        print
        list_and_exit = True
    if options.list_styles:
        for x in plugin_list("style"): print x[0],
        print
        list_and_exit = True
    if options.list_geometries:
        for x in plugin_list("geom"): print x[0],
        print
        list_and_exit = True
    if options.list_layouts:
        for x in plugin_list("layouts"): print x[0],
        print
        list_and_exit = True
    if list_and_exit: sys.exit(0)

    plugin_paths = get_plugin_paths()
    Language = import_plugin(plugin_paths, "lang", "language", "languages", "--list-languages", options.lang)
    Style = import_plugin(plugin_paths, "style", "style", "styles", "--list-styles", options.style)
    Geometry = import_plugin(plugin_paths, "geom", "geometry", "geometries", "--list-geometries", options.geom)
    Layout = import_plugin(plugin_paths, "layouts", "layout", "layouts", "--list-layouts", options.layout)

    for x in argv2:
        if '=' in x: x = x[0:x.find('=')]
        if not Layout.parser.has_option(x):
            parser.error("invalid option %s; use --help (-h) or --layout-help (-?) to see available options" % x)

    (loptions,largs) = Layout.parser.parse_args(argv2)

    if options.layouthelp:
        #print "Help for layout:", options.layout
        Layout.parser.print_help()
        sys.exit(0)

    if options.examples:
        print_examples()
        sys.exit(0)

    # we can put it separately together with Layout; but we load Layout *after* lang,style,geom
    if len(args) < 1 or len(args) > 3:
        parser.print_help()
        sys.exit(0)

    #if (len(args[-1]) == 4 and args[-1].isdigit()):
    #    print "WARNING: file name '%s' looks like a year, writing anyway..." % args[-1]

    # the usual "beware of exec()" crap applies here... but come on,
    # this is a SCRIPTING language, you can always hack the source code!!!
    if options.lang_assign:
        for x in options.lang_assign: exec "Language.%s" % x
    if options.style_assign:
        for x in options.style_assign: exec "Style.%s" % x
    if options.geom_assign:
        for x in options.geom_assign: exec "Geometry.%s" % x

    calendar.long_month_name = Language.long_month_name
    calendar.long_day_name = Language.long_day_name
    calendar.short_month_name = Language.short_month_name
    calendar.short_day_name = Language.short_day_name

    if len(args) == 1:
        Year = time.localtime()[0]
        Month, MonthSpan = 1, 12
        Outfile = args[0]
    elif len(args) == 2:
        Year = parse_year(args[0])
        Month, MonthSpan = 1, 12
        Outfile = args[1]
    elif len(args) == 3:
        Month, MonthSpan = parse_month_range(args[0])
        Year = parse_year(args[1])
        Outfile = args[2]

    if MonthSpan == 0:
        sys.exit("callirhoe: empty calendar requested, aborting")

    Geometry.landscape = options.landscape
    xcairo.XDPI = options.dpi
    Geometry.pagespec = options.paper
    Geometry.border = options.border

    hprovider = holiday.HolidayProvider(Style.dom, Style.dom_weekend,
                                 Style.dom_holiday, Style.dom_weekend_holiday,
                                 Style.dom_multi, Style.dom_weekend_multi, options.multiday_holidays)

    if options.holidays:
        for f in options.holidays:
            hprovider.load_holiday_file(f)

    if options.long_daynames:
        Language.day_name = Language.long_day_name
    else:
        Language.day_name = Language.short_day_name

    if options.short_monthnames:
        Language.month_name = Language.short_month_name
    else:
        Language.month_name = Language.long_month_name

    renderer = Layout.CalendarRenderer(Outfile, Year, Month, MonthSpan,
                                        (Style,Geometry,Language), hprovider, _version, loptions)
    renderer.render()
