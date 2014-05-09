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

# --- layouts._base ---

import optparse
from lib.xcairo import *
from lib.geom import *

def get_parser():
    parser = optparse.OptionParser(usage="%prog (...) --layout classic [options] (...)",add_help_option=False)
    parser.add_option("--rows", type="int", default=0, help="force grid rows [%default]")
    parser.add_option("--cols", type="int", default=0,
                      help="force grid columns [%default]; if ROWS and COLS are both non-zero, "
                      "calendar will span multiple pages as needed; if one value is zero, it "
                      "will be computed automatically in order to fill exactly 1 page")
    parser.add_option("--grid-order", choices=["row","column"],default="row",
                      help="either `row' or `column' to set grid placing order row-wise or column-wise [%default]")
    parser.add_option("--z-order", choices=["auto", "increasing", "decreasing"], default="auto",
                      help="either `increasing' or `decreasing' to set whether next month (in grid order) "
                      "lies above or below the previously drawn month; this affects shadow casting, "
                      "since rendering is always performed in increasing z-order; specifying `auto' "
                      "selects increasing order if and only if sloppy boxes are enabled [%default]")
    parser.add_option("--month-with-year", action="store_true", default=False,
                      help="displays year together with month name, e.g. January 1980; suppresses year from footer line")
    parser.add_option("--short-monthnames", action="store_true", default=False,
                      help="user the short version of month names (defined in language file) [%default]")
    parser.add_option("--long-daynames", action="store_true", default=False,
                    help="user the long version of day names (defined in language file) [%default]")
    parser.add_option("--long-daycells", action="store_const", const=0.0, dest="short_daycell_ratio",
                      help="force use of only long daycells")
    parser.add_option("--short-daycells", action="store_const", const=1.0e6, dest="short_daycell_ratio",
                      help="force use of only short daycells")
    parser.add_option("--short-daycell-ratio", type="float", default=2.5,
                      help="ratio threshold for day cells below which short version is drawn [%default]")
    parser.add_option("--no-footer", action="store_true", default=False,
                      help="disable footer line (with year and rendered-by message)")
    parser.add_option("--symmetric", action="store_true", default=False,
                      help="force symmetric mode (equivalent to --geom-var=month.symmetric=1). "
                      "In symmetric mode, day cells are equally sized and all month boxes contain "
                      "the same number of (possibly empty) cells, independently of how many days or "
                      "weeks per month. In asymmetric mode, empty rows are eliminated, by slightly "
                      "resizing day cells, in order to have uniform month boxes.")
    parser.add_option("--padding", type="float", default=None,
                      help="set month box padding (equivalent to --geom-var=month.padding=PADDING); "
                      "month bars look better with smaller padding, while matrix mode looks better with "
                      "larger padding")
    parser.add_option("--no-shadow", action="store_true", default=None,
                      help="disable box shadows")
    parser.add_option("--opaque", action="store_true", default=False,
                      help="make background opaque (white fill)")
    parser.add_option("--swap-colors", action="store_true", default=None,
                      help="swap month colors for even/odd years")
    return parser


class DayCell(object):
    def __init__(day, header, footer, theme, show_day_name):
        self.day = day
        self.header = header
        self.footer = footer
        self.theme = theme
        self.show_day_name = show_day_name

    def _draw_short(self, cr, rect):
        S,G,L = self.theme
        x, y, w, h = rect
        day_of_month, day_of_week = self.day
        draw_box(cr, rect, S.frame, S.bg, mm_to_dots(S.frame_thickness))
        R = rect_rel_scale(rect, G.size[0], G.size[1])
        if self.show_day_name:
            Rdom, Rdow = rect_hsplit(R, *G.mw_split)
        else:
            Rdom = R
        valign = 0 if self.show_day_name else 2
        # draw day of month (number)
        draw_str(cr, text = str(day_of_month), rect = Rdom, stretch = -1, stroke_rgba = S.fg,
                 align = (2,valign), font = S.font, measure = "88")
        # draw name of day
        if self.show_day_name:
            draw_str(cr, text = L.day_name[day_of_week][0], rect = Rdow, stretch = -1, stroke_rgba = S.fg,
                     align = (2,valign), font = S.font, measure = "88")
        # draw header
        if self.header:
            R = rect_rel_scale(rect, G.header_size[0], G.header_size[1], 0, -1.0 + G.header_align)
            draw_str(cr, text = self.header, rect = R, stretch = -1, stroke_rgba = S.header,
                font = S.header_font) # , measure = "MgMgMgMgMgMg"
        # draw footer
        if self.footer:
            R = rect_rel_scale(rect, G.footer_size[0], G.footer_size[1], 0, 1.0 - G.footer_align)
            draw_str(cr, text = self.footer, rect = R, stretch = -1, stroke_rgba = S.footer,
                font = S.footer_font)

    def _draw_long(self, cr, rect):
        S,G,L = self.theme
        x, y, w, h = rect
        day_of_month, day_of_week = self.day
        draw_box(cr, rect, S.frame, S.bg, mm_to_dots(S.frame_thickness))
        R1, Rhf = rect_hsplit(rect, *G.hf_hsplit)
        if self.show_day_name:
            R = rect_rel_scale(R1, G.size[2], G.size[3])
            Rdom, Rdow = rect_hsplit(R, *G.mw_split)
        else:
            Rdom = rect_rel_scale(R1, G.size[0], G.size[1])
        valign = 0 if self.show_day_name else 2
        # draw day of month (number)
        draw_str(cr, text = str(day_of_month), rect = Rdom, stretch = -1, stroke_rgba = S.fg,
                 align = (2,valign), font = S.font, measure = "88")
        # draw name of day
        if self.show_day_name:
            draw_str(cr, text = L.day_name[day_of_week], rect = Rdow, stretch = -1, stroke_rgba = S.fg,
                     align = (0,valign), font = S.font, measure = "M")
        Rh, Rf = rect_vsplit(Rhf, *G.hf_vsplit)
        # draw header
        if self.header:
            draw_str(cr, text = self.header, rect = Rh, stretch = -1, stroke_rgba = S.header, align = (1,2),
                 font = S.header_font)
        # draw footer
        if self.footer:
            draw_str(cr, text = self.footer, rect = Rf, stretch = -1, stroke_rgba = S.footer, align = (1,2),
                 font = S.footer_font)

    def draw(self, cr, rect, short_thres):
        if rect_ratio(rect) < short_thres:
            _draw_short(cr, rect)
        else:
            _draw_long(cr, rect)

