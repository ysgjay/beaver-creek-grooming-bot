"""Sourced resort facts for the public info pages: hours, opening and closing day, trail map, passes,
blackout dates, lift tickets and lessons.

Every fact carries the official page it came from and the date it was last checked. Facts are
re-checked on a seasonal schedule (Young, 11/19/2026): a fact is checked often in the weeks it
changes and gets searched, and monthly otherwise. Closing dates every 2 days from March 1,
opening dates every 2 days from mid-September, passes and blackout dates every 2 days
in March and April (when next season goes on sale), ticket prices weekly in season.

`watch()` runs once a day (/api/facts): it reads each source page, notes when the relevant
text changed, and writes data/facts/status.json listing what is due for a re-check. A changed
page or a due fact is a prompt to re-read the source and update FACTS here; nothing on the
public page changes until a person (or Claude) confirms the new value.
"""
import hashlib
import html
import re
from datetime import date, datetime, timedelta

# value: what the page shows. None = not announced yet (the page says so, with the source).
# Dates are ISO strings; the page renders them as weekday + MM/DD.
# Hand-checked facts for one resort. Shared facts (passes, blackout dates, announced dates) are
# generated below from one source each and filled in for every resort that has no curated value.
CURATED = {
    "beaver-creek": {
        "opening_day": {"value": "2026-11-25", "checked": "2026-11-19",
                        "source": "https://www.beavercreek.com/explore-the-resort/about-the-resort/hours-of-operation.aspx",
                        "source_name": "Beaver Creek: Hours of Operation"},
        "closing_day": {"value": None, "checked": "2026-11-19",
                        "source": "https://www.beavercreek.com/explore-the-resort/about-the-resort/hours-of-operation.aspx",
                        "source_name": "Beaver Creek: Hours of Operation"},
        "lift_hours": {"value": None, "checked": "2026-11-19",
                       "note": "Lift hours for 2026/27 aren't posted yet. The resort says operations begin 11/25.",
                       "source": "https://www.beavercreek.com/explore-the-resort/about-the-resort/hours-of-operation.aspx",
                       "source_name": "Beaver Creek: Hours of Operation"},
        "trail_map": {"value": "https://www.beavercreek.com/-/aemasset/digital-experience-assets-library/destination-resorts/"
                               "beaver-creek/mountain-operations/winter-2026-2027/20261110_BC_winter-trail_map_001.pdf",
                      "label": "Winter 2026/27 trail map (PDF, on beavercreek.com)", "checked": "2026-11-19",
                      "source": "https://www.beavercreek.com/the-mountain/about-the-mountain/trail-map.aspx",
                      "source_name": "Beaver Creek: Trail and Mountain Maps"},
        "passes": {"value": "Epic Pass: unlimited, no blackout dates. Epic Local Pass: 10 days total, shared with Vail "
                            "and Whistler Blackcomb, not valid on peak dates. Epic Day Pass: not valid on peak dates.",
                   "checked": "2026-11-19", "source": "https://www.epicpass.com/passes/epic-local-pass.aspx",
                   "source_name": "Epic Pass: Epic Local Pass"},
        "blackout_dates": {"value": "11/27 to 11/28/2026, 12/26 to 12/31/2026, 1/16/2027 and 2/13 to 2/14/2027. "
                                    "These apply to the Epic Local Pass and Epic Day Pass. The full Epic Pass has none.",
                           "checked": "2026-11-19", "source": "https://www.epicpass.com/info/peak-restricted-dates.aspx",
                           "source_name": "Epic Pass: Restricted Peak Dates"},
        "lift_tickets": {"value": "$211 online for a 1-day adult ticket (ages 13 to 64) on opening day, 11/25, against $250 "
                                  "full price. Child (5 to 12): $146. Prices change by date, and buying 4+ weeks ahead saves the most.",
                         "checked": "2026-11-19", "source": "https://www.beavercreek.com/plan-your-trip/lift-access/tickets.aspx",
                         "source_name": "Beaver Creek: Lift Tickets"},
        "lessons": {"value": "Child group lessons, adult group lessons (including first-time lessons) and Epic Ascent "
                             "private lessons. Kids save 20% on the third straight day of group lessons and every day after, "
                             "and Epic pass holders get 20% off group lessons.",
                    "checked": "2026-11-19", "source": "https://www.beavercreek.com/plan-your-trip/ski-and-ride-lessons.aspx",
                    "source_name": "Beaver Creek: Ski & Snowboard Lessons"},
    },
    "copper": {
        "opening_day": {"value": "2026-11-08", "checked": "2026-11-19",
                        "source": "https://www.coppercolorado.com/events-activities/events-calendar/opening-day-2627/",
                        "source_name": "Copper Mountain: 26/27 Opening Day"},
        "closing_day": {"value": None, "checked": "2026-11-19",
                        "source": "https://www.coppercolorado.com/events-activities/events-calendar/closing-weekend/",
                        "source_name": "Copper Mountain: Closing Weekend",
                        "note": "Copper's closing weekend page still shows last season's dates."},
        "lift_hours": {"value": "Base area lifts 9 AM to 4 PM. Storm King, Resolution, Blackjack and Mountain Chief "
                                "close at 3 PM; Timberline Express, Excelerator, Sierra, Lumberjack and Rendezvous at "
                                "3:30 PM; Three Bears at 2:30 PM. Fast Tracks gets 30 minutes early on American Eagle.",
                       "checked": "2026-11-19",
                       "source": "https://www.coppercolorado.com/the-mountain/trail-lift-info/lift-hours/",
                       "source_name": "Copper Mountain: Lift Hours"},
        "trail_map": {"value": "https://www.coppercolorado.com/the-mountain/trail-area-maps/winter-trail-map/",
                      "label": "2026/27 winter trail maps: Frontside, Copper Bowl, Spaulding Bowl (on coppercolorado.com)",
                      "checked": "2026-11-19",
                      "source": "https://www.coppercolorado.com/the-mountain/trail-area-maps/winter-trail-map/",
                      "source_name": "Copper Mountain: Winter Trail Map"},
        "passes": {"value": "Ikon Pass: unlimited, no blackout dates. Ikon Base Pass: unlimited, with blackout dates. "
                            "Ikon Session Pass: 2, 3 or 4 days total. Copper also sells its own Copper Season Pass.",
                   "checked": "2026-11-19", "source": "https://www.ikonpass.com/en/compare-passes",
                   "source_name": "Ikon Pass: Compare 26/27 Passes"},
        "blackout_dates": {"value": "12/26 to 12/30/2026, 1/16 to 1/17/2027 and 2/13 to 2/14/2027 on the Ikon Base Pass. "
                                    "The full Ikon Pass has none.",
                           "checked": "2026-11-19",
                           "source": "https://www.ikonpass.com/en/help/blackout-dates/what-are-the-ikon-base-pass-blackout-dates",
                           "source_name": "Ikon Pass: Ikon Base Pass blackout dates"},
        "lift_tickets": {"value": None, "note": "Copper prices tickets by date and doesn't list a fixed price. Buy online at "
                                                "least 1 day ahead for the online price; walk-up window rates may be higher.",
                         "checked": "2026-11-19", "source": "https://www.coppercolorado.com/tickets-passes/lift-tickets/tickets/",
                         "source_name": "Copper Mountain: Lift Tickets"},
        "lessons": {"value": "Adult group lessons (18+), youth group lessons (3 to 17), private and family private lessons, "
                             "adult and youth seasonal programs, Copper Guides, Woodward park privates, adult clinics and "
                             "adaptive lessons.",
                    "checked": "2026-11-19", "source": "https://www.coppercolorado.com/lessons-rentals/lessons/",
                    "source_name": "Copper Mountain: Lessons & Programs"},
    },
}


# ---------- hand-checked facts, 11/19/2026 batch (official resort pages; Vail Resorts and a few others read in a browser) ----------

def _c(value, url, page, note=None, checked="2026-11-19", **extra):
    f = {"value": value, "checked": checked, "source": url, "source_name": page}
    if note:
        f["note"] = note
    return dict(f, **extra)


def _map(page_url, page_name, label, maps):
    """A trail map fact: `value` is the official page; `maps` lists each map the resort posts, so big
    mountains with several maps (Vail's Front Side, Back Bowls, Blue Sky) show all of them.
    Each map: {"label", "season", "image" (resort-hosted image, embedded by URL, never copied), "pdf"}."""
    return _c(page_url, page_url, page_name, label=label,
              maps=[dict(zip(("label", "season", "image", "pdf"), m)) for m in maps])


_VR_TIX_NOTE = ("Prices change by date and the advance price needs 7+ days' notice. The Epic 1-Day Pass is sold only "
                "for a limited time, is non-refundable and isn't valid on peak dates.")
_VR_LESSONS = ("Child group lessons ({kids}), adult group lessons ({adults}, including first-timer lessons), private lessons{extra}. "
               "Kids save 20% on the third straight day of group lessons and adults on the second, Epic pass holders get an "
               "extra 20% off group lessons, and a group lesson unlocks discounted lift tickets and rentals.")
_S7 = "https://scene7.vailresorts.com/is/image/vailresorts/{}?wid=4000&fit=constrain,1&resMode=sharp2"
_AS = "https://www.aspensnowmass.com/-/media/aspen-snowmass/documents/pdfs/25-26/2526-mountain-maps/"
_AS_TIX = _c(None, "https://www.aspensnowmass.com/visit/tickets-and-passes/lift-tickets", "Aspen Snowmass: Lift Tickets",
             note="Aspen Snowmass prices tickets by date and doesn't list a fixed 1-day price. Buying 30+ days ahead saves up "
                  "to 25%, 7+ days up to 20%. Kids 6 and under ski free every day. With a group lesson, kids 7 to 17 get an "
                  "$86 lift ticket and adults $174. One ticket works at all four mountains.")
_AS_LESSONS = _c("Child and teen group lessons (ages 2.5 to 17), adult group lessons, private lessons, specialty camps and "
                 "adaptive clinics (Challenge Aspen and Ascendigo), offered at all four mountains. Kids 7 to 17 and adults "
                 "get a discounted lift ticket with a group lesson.",
                 "https://www.aspensnowmass.com/visit/lessons", "Aspen Snowmass: Ski & Snowboard Lessons")


def _as_map(slug_path, name, pdf):
    page = f"https://www.aspensnowmass.com/four-mountains/{slug_path}/trail-maps"
    return _map(page, f"{name}: Trail Maps", f"{name} winter trail map (PDF, on aspensnowmass.com)",
                [(f"{name} winter trail map", "2025/26 file, still the one linked for 2026/27", None, _AS + pdf)])


CURATED_1119 = {
    "vail": {
        "lift_tickets": _c("$335 online for a 1-day adult ticket (13+) bought 7+ days ahead (price shown for 11/18). The Epic "
                           "1-Day Pass is $155 while it's on sale.", "https://www.vail.com/plan-your-trip/lift-access/tickets.aspx",
                           "Vail: Lift Tickets", note=_VR_TIX_NOTE),
        "lessons": _c(_VR_LESSONS.format(kids="3 to 15", adults="16+", extra=", Epic Ascent private lessons, adaptive programs, "
                                         "adult signature programs and the DEVO program"),
                      "https://www.vail.com/plan-your-trip/ski-and-ride-lessons.aspx", "Vail: Ski & Snowboard Lessons"),
        "trail_map": _map("https://www.vail.com/the-mountain/about-the-mountain/trail-map.aspx", "Vail: Trail and Mountain Maps",
                          "Winter 2026/27 trail maps: Front Side, Back Bowls, Blue Sky (on vail.com)", [
                              ("Front Side", "2026/27", "https://scene7.vailresorts.com/is/image/vailresorts/20261014_VL_front-side-winter-trail-partners_map_001?wid=4000&hei=2467&fit=constrain,1&resMode=sharp2", None),
                              ("Back Bowls", "2026/27", "https://scene7.vailresorts.com/is/image/vailresorts/20261014_VL_back-bowls-winter-trail-partners_map_001-1?wid=4000&hei=2000&fit=constrain,1&resMode=sharp2", None),
                              ("Blue Sky Basin", "2026/27", "https://scene7.vailresorts.com/is/image/vailresorts/20261014_VL_blue-sky-winter-trail-partners_map_001-1?wid=4000&hei=3111&fit=constrain,1&resMode=sharp2", None)]),
    },
    "breckenridge": {
        "lift_tickets": _c("$299 online for a 1-day adult ticket (13+) bought 7+ days ahead (price shown for 11/18). The Epic "
                           "1-Day Pass is $155 while it's on sale.",
                           "https://www.breckenridge.com/plan-your-trip/lift-access/tickets.aspx", "Breckenridge: Lift Tickets",
                           note=_VR_TIX_NOTE + " Breckenridge limits tickets each day, and buying 4+ weeks ahead saves the most."),
        "lessons": _c(_VR_LESSONS.format(kids="3 to 14", adults="15+", extra=", women's programs, seasonal youth programs, "
                                         "Breck Club, Teen Camp and adaptive programs"),
                      "https://www.breckenridge.com/plan-your-trip/ski-and-ride-lessons.aspx", "Breckenridge: Ski & Snowboard Lessons"),
        "trail_map": _map("https://www.breckenridge.com/the-mountain/about-the-mountain/trail-map.aspx",
                          "Breckenridge: Trail and Mountain Maps", "Winter 2026/27 trail map (on breckenridge.com)", [
                              ("Winter trail map, five peaks", "2026/27", _S7.format("20261103_BR_winter-trail_map_001"),
                               "https://www.breckenridge.com/-/aemasset/digital-experience-assets-library/destination-resorts/breckenridge/mountain-operations/winter-2026-2027/20261103_BR_winter-trail_map_001.pdf")]),
    },
    "keystone": {
        "lift_tickets": _c("$229 online for a 1-day adult ticket (13+) bought 7+ days ahead (price shown for 11/18). The Epic "
                           "1-Day Pass is $124 while it's on sale.",
                           "https://www.keystoneresort.com/plan-your-trip/lift-access/tickets.aspx", "Keystone: Lift Tickets",
                           note=_VR_TIX_NOTE),
        "lessons": _c(_VR_LESSONS.format(kids="3 to 14", adults="15+", extra=", seasonal youth programs and adaptive programs"),
                      "https://www.keystoneresort.com/plan-your-trip/ski-and-ride-lessons.aspx", "Keystone: Ski & Snowboard Lessons"),
        "trail_map": _map("https://www.keystoneresort.com/the-mountain/about-the-mountain/trail-map.aspx",
                          "Keystone: Trail and Mountain Maps", "Winter 2026/27 trail map (on keystoneresort.com)", [
                              ("Winter trail map, three peaks", "2026/27", _S7.format("20261020_KY_winter-trail_map_001"),
                               "https://www.keystoneresort.com/-/aemasset/digital-experience-assets-library/destination-resorts/keystone/mountain-operations/winter-2026-2027/20261020_KY_winter-trail_map_001.pdf")]),
    },
    "beaver-creek": {
        "trail_map": dict(CURATED["beaver-creek"]["trail_map"], maps=[{
            "label": "Winter trail map", "season": "2026/27", "image": _S7.format("20261110_BC_winter-trail_map_001"),
            "pdf": CURATED["beaver-creek"]["trail_map"]["value"]}]),
    },
    "crested-butte": {
        "lift_tickets": _c("$199 online for a 1-day adult ticket (13+) on opening day, 11/25, bought 7+ days ahead.",
                           "https://www.skicb.com/plan-your-trip/lift-access/tickets.aspx", "Crested Butte: Lift Tickets",
                           note="Prices change by date and the advance price needs 7+ days' notice."),
        "lessons": _c(_VR_LESSONS.format(kids="3 to 15", adults="15+", extra=", the Mountain Sports Team, kids' winter programs, "
                                         "women's programs and Ski with an Olympian"),
                      "https://www.skicb.com/plan-your-trip/ski-and-ride-lessons.aspx", "Crested Butte: Ski & Snowboard Lessons"),
        "trail_map": _map("https://www.skicb.com/the-mountain/about-the-mountain/trail-maps.aspx", "Crested Butte: Trail Maps",
                          "Winter trail map (PDF, on skicb.com)", [
                              ("Winter trail map", "2025/26 file, still the one linked", None,
                               "https://www.skicb.com/-/aemasset/sitecore/crested-butte/maps/winter-2025-2026/20251103_CB_winter-trail_map_001.pdf")]),
    },
    "park-city": {
        "lift_tickets": _c("$325 online for a 1-day adult ticket (13+) on opening day, 11/20, bought 7+ days ahead. The Epic "
                           "1-Day Pass is $155 while it's on sale.",
                           "https://www.parkcitymountain.com/plan-your-trip/lift-access/tickets.aspx", "Park City: Lift Tickets",
                           note=_VR_TIX_NOTE),
        "lessons": _c(_VR_LESSONS.format(kids="3 to 14", adults="15+", extra=", local youth programs, adult programs and "
                                         "adaptive lessons"),
                      "https://www.parkcitymountain.com/plan-your-trip/ski-and-ride-lessons.aspx", "Park City: Ski & Ride Lessons"),
        "trail_map": _map("https://www.parkcitymountain.com/the-mountain/about-the-mountain/trail-map.aspx",
                          "Park City: Trail Map", "Winter trail map (PDF, on parkcitymountain.com)", [
                              ("Winter trail map, Park City and Canyons", "2025/26 file, still the one linked", None,
                               "https://www.parkcitymountain.com/-/aemasset/sitecore/park-city/maps/20251114_PC_winter-trail_map_001.pdf")]),
    },
    "telluride": {
        "lift_tickets": _c("From $164 online for a 1-day lift ticket. Pricing varies by date.",
                           "https://shop.tellurideskiresort.com/s/winter-lift-tickets", "Telluride: Winter Lift Tickets",
                           note="Buy in advance for the best rate. Group lessons can add a discounted lift ticket."),
        "lessons": _c("Children's group lessons (Otters 3 to 4, Bears 5 to 6, Eagles 7 to 14), Cubs Camp nursery lessons "
                      "(2.5 to 4), adult group lessons (full, half and 3-day), private and Private Premier lessons, a 3-day "
                      "steep and off-piste program, Kids Snow Camp (5 to 10) and Telluride Adaptive Sports. Lessons cost "
                      "less from 12/5 to 12/17, and group lessons unlock discounted lift tickets and rentals.",
                      "https://tellurideskiresort.com/ski-school/", "Telluride: Ski School"),
        "trail_map": _map("https://tellurideskiresort.com/mountain/", "Telluride: The Mountain",
                          "Winter trail map plus Palmyra and Revelation Bowl maps (on tellurideskiresort.com)", [
                              ("Winter trail map", "2024/25 file, still the one linked",
                               "https://tellurideskiresort.com/wp-content/uploads/2425_TSR_Trail-Map_layered-trailmap.jpg",
                               "https://tellurideskiresort.com/wp-content/uploads/2425_TSR_Trail-Map_layered-trailmap.pdf"),
                              ("Palmyra Peak", "2023/24", "https://tellurideskiresort.com/wp-content/uploads/palmyra-23.24.png", None),
                              ("Revelation Bowl", "2023/24", "https://tellurideskiresort.com/wp-content/uploads/revvy-23.24-1.png", None)]),
    },
    "snowmass": {"lift_tickets": _AS_TIX, "lessons": _AS_LESSONS,
                 "trail_map": _as_map("snowmass", "Snowmass", "2526snowmass-map-layeredwebsite.pdf")},
    "aspen-mountain": {"lift_tickets": _AS_TIX, "lessons": _AS_LESSONS,
                       "trail_map": _as_map("aspen-mountain", "Aspen Mountain", "2526aspenmountainwebsite.pdf")},
    "aspen-highlands": {"lift_tickets": _AS_TIX, "lessons": _AS_LESSONS,
                        "trail_map": _as_map("aspen-highlands", "Aspen Highlands", "2526highlands-map-layeredwebsite.pdf")},
    "buttermilk": {"lift_tickets": _AS_TIX, "lessons": _AS_LESSONS,
                   "trail_map": _as_map("buttermilk", "Buttermilk", "2526buttermilk-map-layeredwebsite.pdf")},
    "steamboat": {
        "lift_tickets": _c(None, "https://www.steamboat.com/plan-your-trip/lift-tickets-ski-pass", "Steamboat: Lift Tickets",
                           note="Steamboat doesn't list a fixed price; prices shift by date. It advertises up to 30% off when "
                                "you book by 11/27. A day ticket includes night skiing that day, and late-afternoon tickets "
                                "are sold only on site."),
        "lessons": _c("Group lessons, private lessons, Family Private Experience, Learn 2 Ski or Ride (2-day beginner series), "
                      "afternoon beginner group lessons, seasonal programs (ages 3 to 18+), a 3-day camp with Olympian Deb "
                      "Armstrong, and private and Heli-Ready guided experiences. Booking early saves up to 30%.",
                      "https://www.steamboat.com/plan-your-trip/snowboarding-ski-lessons", "Steamboat: Snowboard & Ski Lessons"),
        "trail_map": _map("https://www.steamboat.com/the-mountain/trail-map/adventure-map", "Steamboat: Adventure Map",
                          "Winter 2026/27 Adventure Map (on steamboat.com)", [
                              ("Adventure Map", "2026/27",
                               "https://www.steamboat.com/-/media/steamboat/maps/winter-26-27/steamboat-adventure-map-final-2026.jpg?rev=0e2ed2aab7354f22ac7745067e9ff9af",
                               None)]),
    },
    "winter-park": {
        "lift_tickets": _c("From $113 online for a 1-day adult ticket, all season with no blackout dates. Thursday tickets are "
                           "$89 (1/7 to 2/25/2027, with blackout dates).",
                           "https://www.winterparkresort.com/plan-your-trip/lift-tickets-ski-pass", "Winter Park: Tickets & Passes",
                           note="Booking online 48+ hours ahead saves up to 40%. Tickets are refundable."),
        "lessons": _c("Kids group lessons (full day, lunch included), adult group lessons (morning or afternoon), Learn to Ski "
                      "and Ride packages, multi-week lessons, Flex 5-packs, private and early-season private lessons, "
                      "60-minute Pro Tips, skills clinics, a Spanish clinic, and adaptive lessons through the NSCD. Winter Park "
                      "and Ikon pass holders get 10% off group lessons booked online, and kids get a free lift ticket with a "
                      "kids group lesson booked by 11/30.",
                      "https://www.winterparkresort.com/plan-your-trip/snowboard-ski-lessons", "Winter Park: Snowboard & Ski Lessons"),
        "trail_map": _map("https://www.winterparkresort.com/the-mountain/mountain-information/maps", "Winter Park: Trails and Maps",
                          "Winter 2026/27 trail map (PDF, on winterparkresort.com)", [
                              ("Winter trail map", "2026/27", None,
                               "https://www.winterparkresort.com/-/media/winter-park/winter/winterparkresort_wintertrailmap.pdf?rev=3913478cfedb4536a70c66c41ae30530")]),
    },
    "arapahoe-basin": {
        "opening_day": _c("2026-10-28", "https://www.denvergazette.com/2026/10/28/photos-ski-season-comes-early-as-arapahoe-basin-opens/",
                          "Denver Gazette: Arapahoe Basin opens",
                          note="Ikon lists A-Basin as open; the resort's own pages don't print the date."),
        "closing_day": _c(None, "https://www.arapahoebasin.com/tickets-and-passes/", "Arapahoe Basin: Tickets & Passes",
                          note="A-Basin lists closing day 2027 as TBD."),
        "lift_tickets": _c(None, "https://www.arapahoebasin.com/tickets-and-passes/", "Arapahoe Basin: Tickets & Passes",
                           note="Full-day ticket prices vary by date, and the sooner you buy the bigger the discount. Tickets "
                                "must be bought online in advance and may sell out."),
        "lessons": _c("Group lessons, private lessons (including 4 for 3 early-season privates), clinics and guided tours (15+), "
                      "Lil Kids Club (3 to 4), Kids Club Arapahoe (5 to 12), Xtreme Teens (11 to 14), the Legendary Learning "
                      "Package (4 lessons with lift access and rentals, then a $119 season pass), and adaptive programs with "
                      "the BOEC.", "https://www.arapahoebasin.com/lessons/", "Arapahoe Basin: Ski School"),
        "trail_map": _map("https://www.arapahoebasin.com/trail-maps/", "Arapahoe Basin: Trail Maps",
                          "Full trail map plus Front Side, Montezuma Bowl and East Wall maps (on arapahoebasin.com)", [
                              ("Full trail map", "2025", None, "https://www.arapahoebasin.com/uploaded/trailmaps/a%20basin%20map%202025.pdf"),
                              ("Front Side, Pallavicini and The Beavers", "2023 file", None,
                               "https://www.arapahoebasin.com/uploaded/trailmaps/a%20basin%20front-01.2%2009182023forweb.pdf"),
                              ("Montezuma Bowl", "2023 file", None,
                               "https://www.arapahoebasin.com/uploaded/trailmaps/a%20basin%20zuma-01.2%2009182023forweb.pdf"),
                              ("East Wall", "Not dated", "https://www.arapahoebasin.com/uploaded/trailmaps/east-wall.jpg", None)]),
    },
    "eldora": {
        "opening_day": _c(None, "https://www.ikonpass.com/en/opening-closing-dates", "Ikon Pass: Opening and Closing Dates",
                          note="Eldora hasn't set a date. Ikon lists it as TBA, and Eldora's site counts down to the 26/27 season."),
        "closing_day": _c(None, "https://www.eldora.com/the-mountain/questions/hours-faq/", "Eldora: Hours FAQ",
                          note="Eldora usually runs November to April and hasn't posted a closing day."),
        "lift_tickets": _c(None, "https://www.eldora.com/tickets-passes/tickets/", "Eldora: Single Day Tickets",
                           note="All tickets are sold online and cost less the earlier you buy. Tickets bought in person at "
                                "the Indian Peaks Lodge get no discount."),
        "lessons": _c("Multi-week youth programs, adult programs, Learn in 3 (a 3-step beginner program), and single-day "
                      "private, group and Nordic lessons. Everything is sold online, and buying ahead saves the most.",
                      "https://www.eldora.com/lessons-rentals/ski-ride-school/", "Eldora: Ski & Ride School"),
        "trail_map": _map("https://www.eldora.com/the-mountain/maps/alpine-trail-map/", "Eldora: Alpine Trail Map",
                          "Alpine trail map (on eldora.com)", [
                              ("Alpine trail map", "2025/26 file, still the one linked",
                               "https://cms.eldora.com/sites/default/files/inline-images/Eldora_25.26_Alpine%20Map_Web.jpg",
                               "https://cms.eldora.com/sites/default/files/2025-11/Eldora_25.26_Alpine%20Map_Web.pdf")]),
    },
    "deer-valley": {
        "lift_hours": _c(None, "https://www.deervalley.com/explore-the-mountain/hours-of-operation", "Deer Valley: Hours of Operation",
                         note="Deer Valley hasn't posted 2026/27 lift hours yet. Ikon lists opening day as 12/5."),
        "lift_tickets": _c(None, "https://www.deervalley.com/plan-your-trip/tickets-and-passes/lift-tickets", "Deer Valley: Lift Tickets",
                           note="Deer Valley caps tickets each day and shows prices by date on its booking calendar. Ages: "
                                "adult 13 to 64, child 5 to 12, senior 65+, tot 4 and under. Learning Area tickets are $68. "
                                "Holidays usually sell out, so buy ahead."),
        "lessons": _c("Private lessons (3 to 18+), adult group lessons of up to 4 (18+), Teen Escape (13 to 17), Adventure Club "
                      "(7 to 12), Reindeer Club (5 to 6), Bambi Club (4), Fawn Special (3), a women's 3-day program, "
                      "multi-week kids programs, the Ted Ligety Performance Camp (2/5 to 2/7/2027) and adaptive lessons with "
                      "the National Ability Center. Deer Valley is ski-only.",
                      "https://www.deervalley.com/plan-your-trip/ski-school", "Deer Valley: Ski School"),
        "trail_map": _map("https://www.deervalley.com/explore-the-mountain/interactive-grooming-map", "Deer Valley: Trail Maps",
                          "Winter 2026/27 trail map (on deervalley.com)", [
                              ("Winter trail map", "2026/27", None,
                               "https://www.deervalley.com/-/media/deer-valley/skier-services/maps/DeerValleyWinterTrailMap2627Compressed")]),
    },
    "solitude": {
        "lift_tickets": _c(None, "https://www.solitudemountain.com/plan-your-trip/snowboarding-ski-lift-tickets-passes",
                           "Solitude: Lift Tickets & Season Pass",
                           note="Solitude prices vary by date; buying online ahead locks in the lowest price. Kids 4 and under "
                                "ski free. Multi-day S-Cards and transferable Ticket Paks bring days under $100."),
        "lessons": _c("Group lessons (including first-timer lessons), private lessons for up to 5, Team Solitude (all-mountain, "
                      "freeride and race for kids and teens), Cruisers multi-week kids programs, skills camps and clinics, and "
                      "seasonal programs including Women on Wednesdays and Women on Weekends. Multi-pack lesson vouchers save "
                      "money and have no blackout days.",
                      "https://www.solitudemountain.com/plan-your-trip/snowboarding-ski-lessons", "Solitude: Ski & Snowboard Lessons"),
        "trail_map": _map("https://www.solitudemountain.com/mountain-and-village/conditions-and-maps", "Solitude: Conditions & Maps",
                          "Winter 2026/27 trail map (PDF, on solitudemountain.com)", [
                              ("Winter trail map", "2026/27", None,
                               "https://www.solitudemountain.com/-/media/Solitude/Trail-Map-PDFs/Solitude_Winter_Trail_Map_2627.pdf")]),
    },
    "brighton": {
        "opening_day": _c("2026-11-24", "https://www.brightonresort.com", "Brighton: Home",
                          note="Explorer and Majestic are planned to run 9 AM to 4 PM.", checked="2026-11-21"),
        "closing_day": _c(None, "https://www.brightonresort.com", "Brighton: Home", note="Not announced."),
        "lift_hours": _c("9 AM to 4 PM daily from 11/24 until night riding begins.",
                         "https://www.brightonresort.com/hours", "Brighton: Hours of Operation",
                         note="Night riding hours aren't posted yet. Brighton rides Sunday nights this season, and its "
                              "weekly closed day moves to Tuesday.", checked="2026-11-21"),
        "lift_tickets": _c("From $72 for winter lift tickets (all-day, afternoon and night tickets).",
                           "https://www.brightonresort.com/lift-tickets", "Brighton: Lift Tickets",
                           note="Prices vary by ticket type, age and date."),
        "lessons": _c("Kids group lessons (4 to 12), adult group lessons (13+), private lessons (3+), 4-pack group lessons (4+), "
                      "a Learn to Ride package (13+, lesson, rental and learner ticket; 50% off before 12/18) and Thursday "
                      "night group lessons (8+).",
                      "https://www.brightonresort.com/lessons/daily-winter-lessons", "Brighton: Daily Winter Lessons"),
    },
    "alta": {
        "lift_tickets": _c(None, "https://www.alta.com/tickets-and-passes", "Alta: Lift Tickets and Season Passes",
                           note="Alta sells online rates, window rates and window-only tickets but doesn't list a fixed "
                                "price. Alta is skiers-only; snowboarding isn't allowed."),
        "lessons": _c("Alf Engen Ski School: private lessons and private guided tours, adult classes, and kids classes and camps. "
                      "Ski only.", "https://www.alta.com/ski-school", "Alta: Alf Engen Ski School"),
        "trail_map": _map("https://www.alta.com/plan-your-trip#maps", "Alta: Plan Your Trip, Maps",
                          "Winter 2026/27 trail map (on alta.com)", [
                              ("Winter trail map", "2026/27",
                               "https://res.cloudinary.com/altaskiarea/image/upload/f_auto,q_auto/v1793054037/resources/Maps/AltaSkiArea_TrailMap_2026-27.jpg",
                               "https://res.cloudinary.com/altaskiarea/image/upload/v1793054038/resources/Maps/26_27_Alta_Trailmap_WEB.pdf")]),
    },
    "snowbird": {
        "lift_hours": _c(None, "https://www.snowbird.com/the-mountain/mountain-report/lift-trail-report/", "Snowbird: Lift & Trail Report",
                         note="Snowbird hasn't posted 2026/27 lift hours. It plans to open lift-served terrain 11/27."),
        "lift_tickets": _c("From $195 for a 1-day adult ticket (13 to 64), $117 youth (7 to 12), $166 senior (65+). Kids 6 and "
                           "under ski free.", "https://www.snowbird.com/tickets-passes/tickets/", "Snowbird: Lift Tickets",
                           note="Prices rise on peak and holiday dates (holiday: 12/24 to 1/1, 1/16 to 1/17, 2/13 to 2/15). "
                                "Buying online 2+ weeks ahead saves up to 15% over the window."),
        "lessons": _c("Private and group ski and snowboard lessons from first-timer to advanced, multi-week programs, camps, "
                      "women's programs, guiding (including snowcat skiing) and AIARE avalanche classes.",
                      "https://www.snowbird.com/guiding-lessons/programs/", "Snowbird: Mountain Guiding & Ski School"),
        "trail_map": _map("https://www.snowbird.com/the-mountain/maps/winter-trail-map/", "Snowbird: Winter Trail Map",
                          "Winter 2026/27 trail map (on snowbird.com)", [
                              ("Winter trail map", "2026/27",
                               "https://cms.snowbird.com/sites/default/files/2026-10/TrailMap_1920x2318_2627.jpg", None)]),
    },
    "snowbasin": {
        "lift_tickets": _c(None, "https://www.snowbasin.com/tickets-passes/lift-tickets/", "Snowbasin: Lift Tickets",
                           note="Snowbasin doesn't list a fixed price; buying online ahead gets the best price. Ages: adult "
                                "and teen 13 to 64, youth 5 to 12, senior 65+. Kids 4 and under ski free."),
        "lessons": _c("Adult all-day group lessons (13+), youth half- and full-day group lessons (3 to 12), private lessons for "
                      "up to 5, Learn & Earn for first-timers (4+, lessons, season rentals and a season pass), multi-week youth "
                      "programs, Women of Winter and adaptive lessons with OVAS.",
                      "https://www.snowbasin.com/lessons/", "Snowbasin: Ski and Snowboard Lessons"),
        "trail_map": _map("https://www.snowbasin.com/the-mountain/trail-maps/", "Snowbasin: Trail Maps",
                          "Winter trail map (on snowbasin.com)", [
                              ("Winter trail map", "2025/26 file, still the one linked",
                               "https://www.snowbasin.com/azure/snowbasin/media/siteassets/pdf/maps/winter/winter-trail-map-2025-26-(22-5in-x-12in).jpg?w=4000&mode=crop&scale=both",
                               "https://www.snowbasin.com/getmedia/969afd05-b39b-4ecd-b123-6c0669d41d77/Winter-Trail-Map-2025-26-(22-5in-x-12in)-for-Ikon-reduced.pdf")]),
    },
}
for _slug, _kinds in CURATED_1119.items():
    CURATED.setdefault(_slug, {}).update(_kinds)


# ---------- shared facts: one official source, many resorts ----------
# Re-checking one of these pages updates every resort that uses it. See docs/RESORT_FACTS.md.

CHECKED_SHARED = "2026-11-19"
EPIC_PASS = ("https://www.epicpass.com/passes/epic-pass.aspx", "Epic Pass: Epic Pass resort access")
EPIC_LOCAL = ("https://www.epicpass.com/passes/epic-local-pass.aspx", "Epic Pass: Epic Local Pass")
EPIC_PEAK = ("https://www.epicpass.com/info/peak-restricted-dates.aspx", "Epic Pass: Restricted Peak Dates")
EPIC_PEAK_DATES = "11/27 to 11/28/2026, 12/26 to 12/31/2026, 1/16/2027 and 2/13 to 2/14/2027"
IKON_COMPARE = ("https://www.ikonpass.com/en/compare-passes", "Ikon Pass: Compare 26/27 Passes")
IKON_BASE_BLACKOUTS = ("https://www.ikonpass.com/en/help/blackout-dates/what-are-the-ikon-base-pass-blackout-dates",
                       "Ikon Pass: Ikon Base Pass blackout dates")
IKON_BASE_DATES = "12/26 to 12/30/2026, 1/16 to 1/17/2027 and 2/13 to 2/14/2027"
IKON_DATES = ("https://www.ikonpass.com/en/opening-closing-dates", "Ikon Pass: Opening and Closing Dates")
VR_DATES = ("https://news.vailresorts.com/2026-08-18-Is-Winter-About-to-Show-Off-Vail-Resorts-Announces-2026-27-Opening-Dates-as-Super-El-Nino-Builds-Anticipation-for-Great-Powder",
            "Vail Resorts: 2026/27 opening dates")

# Epic access per resort, word for word from the Epic Pass and Epic Local Pass pages: (Epic Pass, Epic Local Pass).
EPIC_ACCESS = {
    "vail": ("unlimited, no blackout dates", "10 days total, shared with Beaver Creek and Whistler Blackcomb, not valid on peak dates"),
    "beaver-creek": ("unlimited, no blackout dates", "10 days total, shared with Vail and Whistler Blackcomb, not valid on peak dates"),
    "breckenridge": ("unlimited, no blackout dates", "unlimited, including peak dates"),
    "keystone": ("unlimited, no blackout dates", "unlimited, including peak dates"),
    "crested-butte": ("unlimited, no blackout dates", "unlimited, including peak dates"),
    "park-city": ("unlimited, no blackout dates", "unlimited, not valid on peak dates"),
    "telluride": ("7 days total, then 50% off lift tickets", None),
}
# Ikon access per resort from the Compare Passes page: (Ikon Pass, Ikon Base Pass, Ikon Session Pass); None = not included.
IKON_ACCESS = {
    "arapahoe-basin": ("unlimited", "unlimited", "2, 3 or 4 days"),
    "snowmass": ("7 days, shared across Aspen Mountain, Snowmass, Aspen Highlands and Buttermilk", "Snowmass only", "5 days"),
    "aspen-mountain": ("7 days, shared across Aspen Mountain, Snowmass, Aspen Highlands and Buttermilk", None, "5 days"),
    "aspen-highlands": ("7 days, shared across Aspen Mountain, Snowmass, Aspen Highlands and Buttermilk", None, "5 days"),
    "buttermilk": ("7 days, shared across Aspen Mountain, Snowmass, Aspen Highlands and Buttermilk", None, "5 days"),
    "eldora": ("unlimited", "unlimited", "2, 3 or 4 days"),
    "steamboat": ("unlimited", "5 days", "2, 3 or 4 days"),
    "winter-park": ("unlimited", "unlimited", "2, 3 or 4 days"),
    "copper": ("unlimited", "unlimited", "2, 3 or 4 days"),
    "alta": ("7 days, shared with Snowbird", None, None),
    "snowbird": ("7 days, shared with Alta", "5 days, Snowbird only", None),
    "brighton": ("7 days", "5 days", "2, 3 or 4 days"),
    "solitude": ("unlimited", "unlimited", "2, 3 or 4 days"),
    "deer-valley": ("7 days, lift reservations required", "3 days, lift reservations required", None),
    "snowbasin": ("7 days", None, None),
}
# Announced opening (and closing) days: slug -> (opening, closing, source).
ANNOUNCED = {
    "vail": ("2026-11-13", None, VR_DATES), "breckenridge": ("2026-11-06", None, VR_DATES),
    "park-city": ("2026-11-20", None, VR_DATES), "crested-butte": ("2026-11-25", None, VR_DATES),
    "keystone": ("2026-10-30", None, ("https://news.vailresorts.com/keystone-opening-2026", "Keystone: 2026/27 Opening Day")),
    "telluride": ("2026-12-05", "2027-04-04", ("https://tellurideskiresort.com/?faqs=how-can-i-submit-a-photo-for-my-pass-prior-to-arrival",
                                              "Telluride: 2026-27 winter season dates")),
    "aspen-mountain": ("2026-11-26", None, IKON_DATES), "snowmass": ("2026-11-26", None, IKON_DATES),
    "aspen-highlands": ("2026-12-12", None, IKON_DATES), "buttermilk": ("2026-12-12", None, IKON_DATES),
    "steamboat": ("2026-11-27", None, ("https://www.steamboat.com/the-mountain/hours-and-operations", "Steamboat: Hours and Operations")), "alta": ("2026-11-20", None, IKON_DATES),
    "snowbird": ("2026-11-27", None, IKON_DATES), "solitude": ("2026-11-19", None, ("https://www.solitudemountain.com/mountain-and-village/mountain-information/hours-of-operation", "Solitude: Hours of Operation")),
    "deer-valley": ("2026-12-05", None, IKON_DATES), "snowbasin": ("2026-11-27", None, IKON_DATES),
    "whistler-blackcomb": ("2026-11-20", None, VR_DATES), "heavenly": ("2026-11-20", None, VR_DATES),
    "northstar": ("2026-11-20", None, VR_DATES), "kirkwood": ("2026-12-04", None, VR_DATES),
    "stevens-pass": ("2026-12-04", None, VR_DATES), "mt-bachelor": ("2026-12-04", None, IKON_DATES),
    "winter-park": ("2026-11-13", "2027-04-18", ("https://www.winterparkresort.com/the-mountain/hours-of-operation", "Winter Park: Hours of Operation")),
}
# Trail map pages checked by hand (we link, never copy the art).
TRAIL_MAPS = {
    "vail": ("https://www.vail.com/the-mountain/about-the-mountain/trail-map.aspx", "Winter 2026/27 trail maps: Front Side, Back Bowls, Blue Sky (on vail.com)"),
    "breckenridge": ("https://www.breckenridge.com/the-mountain/about-the-mountain/trail-map.aspx", "Winter 2026/27 trail map (on breckenridge.com)"),
    "keystone": ("https://www.keystoneresort.com/the-mountain/about-the-mountain/trail-map.aspx", "Trail maps (on keystoneresort.com)"),
}
# Lift hours read from each resort's own hours page: slug -> (value, (url, page name)).
LIFT_HOURS = {
    "vail": ("9 AM to 3:30 PM daily.", ("https://www.vail.com/explore-the-resort/about-the-resort/hours-of-operation.aspx", "Vail: Hours of Operation")),
    "breckenridge": ("Chairlifts 9 AM to 4 PM. The gondola (BreckConnect) runs 8:30 AM to 5 PM, last upload 4:30 PM. High alpine lifts may open later with conditions.",
                     ("https://www.breckenridge.com/explore-the-resort/about-the-resort/hours-of-operation.aspx", "Breckenridge: Hours of Operation")),
    "keystone": ("Chairlifts 9 AM to 4 PM. Early season runs from River Run only: River Run Gondola, Summit Express and Montezuma Express, 9 AM to 4 PM.",
                 ("https://www.keystoneresort.com/explore-the-resort/about-the-resort/hours-of-operation.aspx", "Keystone: Hours of Operation")),
    "crested-butte": ("9 AM to 4 PM daily, starting 11/25.", ("https://www.skicb.com/explore-the-resort/about-the-resort/hours-of-operation.aspx", "Crested Butte: Hours of Operation")),
    "park-city": ("Lifts 9 AM to 4 PM daily. Canyons Village Skyway and Frostwood Gondola 7 AM to 6 PM.",
                  ("https://www.parkcitymountain.com/explore-the-resort/about-the-resort/hours-of-operation.aspx", "Park City Mountain: Hours of Operation")),
    "winter-park": ("9 AM to 4 PM daily through 12/5. From 12/5 to 4/4, lifts open at 8 AM on Saturdays and Sundays.",
                    ("https://www.winterparkresort.com/the-mountain/hours-of-operation", "Winter Park: Hours of Operation")),
    "arapahoe-basin": ("9 AM to 4 PM Monday to Friday, 8:30 AM to 4 PM weekends and select holidays. Lenawee Express and Pallavicini close at 3:30 PM.",
                       ("https://www.arapahoebasin.com/operating-hours-/", "A-Basin: Lift & Dining Operating Hours")),
    "steamboat": ("Christie Peak Express and the Steamboat Gondola 8:30 AM to 4 PM (gondola last download 4:30 PM). Wild Blue Gondola 9 AM to 3 PM. Four Points Express 9:30 AM to 3:15 PM from 12/18.",
                  ("https://www.steamboat.com/the-mountain/hours-and-operations", "Steamboat: Hours and Operations")),
    "eldora": ("9 AM to 4 PM Monday to Friday, 8:30 AM to 4 PM Saturday and Sunday. No night skiing.",
               ("https://www.eldora.com/the-mountain/mountain-info/faqs-policies/", "Eldora: Hours & FAQs")),
    "snowmass": ("9 AM to 3:30 PM.", ("https://www.aspensnowmass.com/four-mountains/snowmass/lift-status", "Snowmass: Lift Status")),
    "aspen-mountain": ("9 AM to 3:30 PM.", ("https://www.aspensnowmass.com/four-mountains/aspen-mountain/lift-status", "Aspen Mountain: Lift Status")),
    "aspen-highlands": ("9 AM to 3:30 PM.", ("https://www.aspensnowmass.com/four-mountains/aspen-highlands/lift-status", "Aspen Highlands: Lift Status")),
    "buttermilk": ("9 AM to 3:30 PM.", ("https://www.aspensnowmass.com/four-mountains/buttermilk/lift-status", "Buttermilk: Lift Status")),
    "alta": ("Lifts start at 9:15 AM. Collins and Sunnyside run to 4:30 PM, Sugarloaf and Wildcat to 4 PM, Supreme to 3:30 PM.",
             ("https://www.alta.com/about", "Alta: About Alta Ski Area")),
    "solitude": ("Early season (to mid-December): most lifts 9 AM to 4 PM; Summit Express and Honeycomb Return 9 AM to 3:30 PM. From mid-December, Apex, Moonbeam and Link open at 8 AM.",
                 ("https://www.solitudemountain.com/mountain-and-village/mountain-information/hours-of-operation", "Solitude: Hours of Operation")),
    "snowbasin": ("9 AM to 4 PM daily.", ("https://www.snowbasin.com/about/faqs/", "Snowbasin: FAQs")),
}
TELLURIDE_HOURS = "Base lifts 9 AM to 4 PM. The free gondola runs 6:30 AM to midnight, 7 days a week."


# ---------- 11/19/2026 batch 2: the 50 shadow resorts (Epic and Ikon pages, then each resort's own pages) ----------
def _src(url, page):
    return (url, page)


EPIC_ACCESS.update({
    "whistler-blackcomb": ("unlimited, no blackout dates", "10 days total, shared with Vail and Beaver Creek, not valid on peak dates"),
    "heavenly": ("unlimited, no blackout dates", "unlimited, not valid on peak dates"),
    "northstar": ("unlimited, no blackout dates", "unlimited, not valid on peak dates"),
    "kirkwood": ("unlimited, no blackout dates", "unlimited, not valid on peak dates"),
    "stowe": ("unlimited, no blackout dates", "unlimited, not valid on peak dates"),
    "stevens-pass": ("unlimited, no blackout dates", "unlimited, including peak dates"),
    "okemo": ("unlimited, no blackout dates", "unlimited, including peak dates"),
    "mount-snow": ("unlimited, no blackout dates", "unlimited, including peak dates"),
    "seven-springs": ("unlimited, no blackout dates", "unlimited, including peak dates"),
})
_IKON_UNL = ("unlimited", "unlimited", "2, 3 or 4 days")
_IKON_7 = ("7 days", "5 days", "2, 3 or 4 days")
IKON_ACCESS.update({
    "mammoth": _IKON_UNL, "palisades-tahoe": _IKON_UNL, "big-bear": _IKON_UNL, "tremblant": _IKON_UNL,
    "sugarbush": _IKON_UNL, "stratton": _IKON_UNL, "snowshoe": _IKON_UNL,
    "crystal-mountain": ("unlimited", "5 days", "2, 3 or 4 days"),
    "mt-bachelor": _IKON_7, "sugarloaf": _IKON_7, "sunday-river": _IKON_7, "loon": _IKON_7, "taos": _IKON_7,
    "revelstoke": _IKON_7, "sun-peaks": _IKON_7,
    "killington": ("7 days, shared with Pico", "5 days, shared with Pico", "2, 3 or 4 days"),
    "big-sky": ("7 days, tram not included", "5 days, tram not included", "2, 3 or 4 days"),
    "banff-sunshine": ("7 days, shared with Lake Louise and Mt. Norquay", "5 days, shared with Lake Louise and Mt. Norquay", "2, 3 or 4 days"),
    "lake-louise": ("7 days, shared with Banff Sunshine and Mt. Norquay", "5 days, shared with Banff Sunshine and Mt. Norquay", "2, 3 or 4 days"),
    "jackson-hole": ("7 days", None, None),
    "sun-valley": ("7 days, shared with Dollar Mountain", None, None),
})
ANNOUNCED.update({
    "jackson-hole": ("2026-11-27", None, IKON_DATES), "crystal-mountain": ("2026-11-27", None, IKON_DATES),
    "sugarbush": ("2026-11-21", None, IKON_DATES), "stratton": ("2026-11-25", None, IKON_DATES),
    "sugarloaf": ("2026-11-20", None, IKON_DATES), "sunday-river": ("2026-11-15", None, IKON_DATES),
    "taos": ("2026-11-26", None, IKON_DATES),
    "heavenly": ("2026-11-20", None, _src("https://www.skiheavenly.com/explore-the-resort/about-the-resort/hours-of-operation.aspx", "Heavenly: Hours of Operation")),
    "big-sky": ("2026-11-25", None, _src("https://www.bigskyresort.com", "Big Sky: Home")),
    "sun-valley": ("2026-11-26", None, _src("https://www.sunvalley.com/The-Mountain/Opening-Day", "Sun Valley: Opening Day")),
    "palisades-tahoe": ("2026-11-21", None, _src("https://www.palisadestahoe.com/events-and-activities/events-calendar/opening-day", "Palisades Tahoe: Opening Day")),
    "tremblant": ("2026-11-26", "2027-04-18", _src("https://www.tremblant.ca/mountain-village/opening-hours", "Tremblant: Opening Hours")),
    "snowshoe": ("2026-12-04", "2027-03-21", _src("https://www.snowshoemtn.com/mountain-info/hours-of-operation", "Snowshoe: Hours of Operation")),
    "revelstoke": ("2026-12-05", None, _src("https://www.revelstokemountainresort.com/mountain/hours-of-operations/", "Revelstoke: Hours of Operation")),
    "sun-peaks": ("2026-11-26", "2027-04-04", _src("https://www.sunpeaksresort.com/ski-ride/the-mountain/winter-hours-of-operation", "Sun Peaks: Winter Hours of Operation")),
    "big-white": ("2026-11-26", "2027-04-04", _src("https://www.bigwhite.com/explore/mountain-info/winter-hours-operation", "Big White: Winter Hours of Operation")),
    "whitefish": ("2026-12-04", "2027-04-04", _src("https://skiwhitefish.com/hours-and-dates/", "Whitefish: Hours & Dates")),
    "wolf-creek": ("2026-11-21", None, _src("https://wolfcreekski.com", "Wolf Creek: Home")),
    "purgatory": ("2026-11-20", None, _src("https://www.purgatory.ski", "Purgatory: Home")),
    "saddleback": ("2026-12-04", None, _src("https://www.saddlebackmaine.com", "Saddleback: Home")),
    "holiday-valley": ("2026-11-27", None, _src("https://www.holidayvalley.com/event/opening-day-2026-27/", "Holiday Valley: Opening Day 2026-27")),
    "waterville-valley": ("2026-11-28", None, _src("https://www.waterville.com", "Waterville Valley: Home")),
    "jay-peak": ("2026-11-27", None, _src("https://jaypeakresort.com", "Jay Peak: Home")),
})
_VR = "/explore-the-resort/about-the-resort/hours-of-operation.aspx"
LIFT_HOURS.update({
    "whistler-blackcomb": ("Base area lifts 9 AM to 3:30 PM from 11/20 to 1/15, 9 AM to 4 PM from 1/16 to 2/12, and 8:30 AM to 4 PM from 2/13 to closing day.",
                           _src("https://www.whistlerblackcomb.com" + _VR, "Whistler Blackcomb: Hours of Operation")),
    "heavenly": ("Opening day hours 9 AM to 4 PM on the Tram, Gun Barrel Express, Patsy's and Powderbowl (California side only).",
                 _src("https://www.skiheavenly.com" + _VR, "Heavenly: Hours of Operation")),
    "northstar": ("Most lifts 9 AM to 4 PM. Big Springs Gondola 8:30 AM to 4 PM, Village Express 8:30 AM to 1 PM, Promised Land and Rendezvous 10 AM to 3 PM. Highlands Gondola 7:45 AM to 8 PM.",
                  _src("https://www.northstarcalifornia.com" + _VR, "Northstar: Hours of Operation")),
    "mount-snow": ("Main lifts 9 AM to 4 PM on weekdays and 8 AM to 4 PM on weekends and holidays. Grand Summit Express 9 AM to 3:30 PM (Fridays, weekends and holidays); North Face lifts close at 3:30 PM.",
                   _src("https://www.mountsnow.com" + _VR, "Mount Snow: Hours of Operation")),
    "mammoth": ("Scheduled lift hours 8:30 AM to 4 PM daily.", _src("https://www.mammothmountain.com/on-the-mountain/hours-of-operation", "Mammoth: Hours of Operation")),
    "killington": ("9 AM to 4 PM Monday to Friday, 8 AM to 4 PM weekends and peak days (11/26 to 11/29, 12/25 to 1/3, 1/16 to 1/18 and 2/13 to 2/15).",
                   _src("https://killington.com/hours", "Killington: Hours")),
    "jackson-hole": ("Most lifts, including the Bridger Gondola, 9 AM to 4 PM. Aerial Tram 9 AM to 3:30 PM, Sublette and Thunder 9:15 AM to 3:40 PM. Apres Vous, Teewinot and the Sweetwater Gondola open at 8:30 AM on weekends and holidays.",
                     _src("https://www.jacksonhole.com/lift-tickets", "Jackson Hole: Lift Tickets")),
    "big-sky": ("9 AM to 4 PM on all open lifts.", _src("https://www.bigskyresort.com/winter-tickets/lift-ticket", "Big Sky: Lift Tickets")),
    "banff-sunshine": ("Chairs 9:30 AM to 4:30 PM, Jackrabbit to 5 PM. Gondola 8:30 AM to 6 PM, to 10:30 PM on Fridays.",
                       _src("https://www.skibanff.com/the-mountain/mountain-report/hours-of-operation", "Banff Sunshine: Hours of Operation")),
    "lake-louise": ("9:30 AM to 4:30 PM daily.", _src("https://www.skilouise.com/hours-of-operation/", "Lake Louise: Hours of Operation")),
    "stratton": ("9 AM to 4 PM Monday to Friday, 8:30 AM to 4 PM weekends and holidays. Summit lifts (Gondola, Ursa, Shooting Star, Snow Bowl) close at 3:30 PM until 1/15.",
                 _src("https://www.stratton.com/the-mountain/hours-of-operation", "Stratton: Hours of Operation")),
    "snowshoe": ("Snowshoe Basin 9 AM to 4:30 PM and Western Territory 9 AM to 4:15 PM daily. Silver Creek 12 to 9 PM Monday to Thursday and 9 AM to 9 PM Friday to Sunday.",
                 _src("https://www.snowshoemtn.com/mountain-info/hours-of-operation", "Snowshoe: Hours of Operation")),
    "revelstoke": ("Early season: Lower Gondola 9 AM to 3 PM, Upper Gondola to 3:10 PM, Stoke and Stellar chairs to 3:30 PM. Closing times move later in mid and late season.",
                   _src("https://www.revelstokemountainresort.com/mountain/hours-of-operations/", "Revelstoke: Hours of Operation")),
    "loon": ("Lifts open at 9 AM Monday to Friday and 8 AM weekends and holidays (12/28 to 1/1, 1/16 to 1/18, 2/13 to 2/21). Closing times vary by lift.",
             _src("https://www.loonmtn.com/hours", "Loon: Hours")),
    "sun-peaks": ("Most chairs 9:30 AM to 4 PM (9 AM from 2/1). Sundance Express 9 AM to 4:15 PM and Morrisey Express 9 AM to 4 PM (8:30 AM from 2/1). West Bowl Express 10 AM to 3:45 PM.",
                  _src("https://www.sunpeaksresort.com/ski-ride/the-mountain/winter-hours-of-operation", "Sun Peaks: Winter Hours of Operation")),
    "whitefish": ("Most chairs 9 AM to 4 PM. Big Mountain Express 9:30 AM to 4 PM, Base Lodge chair 8:45 AM to 4:30 PM, Big Creek Express 9:45 AM to 3:30 PM. Night skiing on Chairs 2, 3 and 6.",
                  _src("https://skiwhitefish.com/hours-and-dates/", "Whitefish: Hours & Dates")),
    "loveland": ("9 AM to 4 PM Monday to Friday, 8:30 AM to 4 PM weekends and designated holidays.",
                 _src("https://skiloveland.com/the-mountain/hours-of-operation/", "Loveland: Hours of Operation")),
    "wolf-creek": ("9 AM to 4 PM on all lifts from 11/21. Normally 8:30 AM to 4 PM.", _src("https://wolfcreekski.com", "Wolf Creek: Home")),
    "big-white": ("Lara's Gondola 7:45 AM to 10 PM Sunday to Thursday and to 11 PM Friday and Saturday. Night skiing 3:30 to 8 PM on the Bullet Express, Plaza Chair and TELUS Park from 12/18 to 1/2 (not 12/24 or 12/31). Daytime chair hours aren't listed.",
                  _src("https://www.bigwhite.com/explore/mountain-info/winter-hours-operation", "Big White: Winter Hours of Operation")),
    "mad-river-glen": ("Main lifts 8:30 AM to 4 PM on weekends and holidays and 9 AM to 4 PM midweek. Birdland Double 9:30 AM to 3 PM.",
                       _src("https://www.madriverglen.com/hours/", "Mad River Glen: Hours of Operation")),
    "bretton-woods": ("9 AM to 3:30 PM.", _src("https://www.brettonwoods.com", "Bretton Woods: Home")),
})
TRAIL_MAPS.update({
    "heavenly": ("https://www.skiheavenly.com/the-mountain/about-the-mountain/trail-map.aspx", "Trail map page (the winter map shown is still 2024/25, on skiheavenly.com)"),
    "northstar": ("https://www.northstarcalifornia.com/the-mountain/about-the-mountain/trail-map.aspx", "Winter trail map (2025/26 file, on northstarcalifornia.com)"),
    "kirkwood": ("https://www.kirkwood.com/the-mountain/about-the-mountain/trail-map.aspx", "Winter trail map (2025/26 file, on kirkwood.com)"),
    "stowe": ("https://www.stowe.com/the-mountain/about-the-mountain/trail-map.aspx", "Winter 2026/27 trail map and base area map (on stowe.com)"),
    "seven-springs": ("https://www.7springs.com/the-mountain/about-the-mountain/trail-map.aspx", "Winter trail map (2025/26 file, on 7springs.com)"),
    "sun-valley": ("https://www.sunvalley.com/the-mountain/maps-guides", "Winter 2026/27 maps: Bald Mountain and Dollar Mountain (on sunvalley.com)"),
    "mammoth": ("https://www.mammothmountain.com/on-the-mountain/winter-trail-map", "Winter trail map (on mammothmountain.com)"),
    "killington": ("https://killington.com/winter-trail-map", "Winter trail map (on killington.com)"),
    "palisades-tahoe": ("https://www.palisadestahoe.com/mountain-information/trail-maps", "Trail maps, Palisades and Alpine (on palisadestahoe.com)"),
    "crystal-mountain": ("https://www.crystalmountainresort.com/the-mountain/trail-maps", "Trail maps (on crystalmountainresort.com)"),
    "banff-sunshine": ("https://www.skibanff.com/the-mountain/lifts-terrain/trail-maps", "Trail maps (on skibanff.com)"),
    "big-bear": ("https://www.bigbearmountainresort.com/mountain-information/trail-maps", "Trail maps, Bear Mountain, Snow Summit and Snow Valley (on bigbearmountainresort.com)"),
    "tremblant": ("https://www.tremblant.ca/mountain-village/maps", "Ski trail maps (on tremblant.ca)"),
    "sugarbush": ("https://www.sugarbush.com/mountain/terrain-and-maps", "Maps and terrain (on sugarbush.com)"),
    "stratton": ("https://www.stratton.com/the-mountain/interactive-trail-map", "Interactive trail map (on stratton.com)"),
    "snowshoe": ("https://www.snowshoemtn.com/mountain-info/maps", "Trail maps (on snowshoemtn.com)"),
    "sugarloaf": ("https://www.sugarloaf.com/mountain-info#mountainmaps", "Mountain maps (on sugarloaf.com)"),
    "revelstoke": ("https://www.revelstokemountainresort.com/discover/about/trail-maps/", "Trail maps (on revelstokemountainresort.com)"),
    "sun-peaks": ("https://www.sunpeaksresort.com/ski-ride/the-mountain/trail-maps-terrain", "Trail maps and terrain (on sunpeaksresort.com)"),
    "whitefish": ("https://skiwhitefish.com/trail-maps/", "Winter trail maps (on skiwhitefish.com)"),
    "grand-targhee": ("https://www.grandtarghee.com/the-mountain/mountain-information/trail-maps", "Trail maps (on grandtarghee.com)"),
    "jay-peak": ("https://jaypeakresort.com/skiing-riding/snow-report-maps/trail-map", "Trail map (on jaypeakresort.com)"),
    "loveland": ("https://skiloveland.com/the-mountain/trail-map-mountain-stats/", "Trail map (on skiloveland.com)"),
    "wolf-creek": ("https://wolfcreekski.com/area-maps/", "Area maps (on wolfcreekski.com)"),
    "big-white": ("https://www.bigwhite.com/explore/mountain-info/maps", "Winter maps (on bigwhite.com)"),
    "powder-mountain": ("https://powdermountain.com/trail-map", "Winter trail map (2025/26 file, on powdermountain.com)"),
    "saddleback": ("https://www.saddlebackmaine.com/trail-maps/", "Trail maps (on saddlebackmaine.com)"),
    "holiday-valley": ("https://www.holidayvalley.com/resort-maps/", "Resort maps (on holidayvalley.com)"),
    "mad-river-glen": ("https://www.madriverglen.com/trail-maps/", "Trail maps (on madriverglen.com)"),
    "tamarack": ("https://tamarackidaho.com/the-mountain/maps", "Resort maps (on tamarackidaho.com)"),
    "mt-baker": ("https://www.mtbaker.us/the-mountain/trail-map/", "Trail map (on mtbaker.us)"),
    "purgatory": ("https://www.purgatory.ski/mountain/purgatory-mountain/trail-maps/", "Trail maps (on purgatory.ski)"),
    "bretton-woods": ("https://www.brettonwoods.com/plan-visit/maps/", "Alpine and Nordic trail maps (on brettonwoods.com)"),
    "taos": ("https://www.skitaos.com/weather", "Resort trail map (on skitaos.com, Lifts & Trails page)"),
})


# ---------- 11/20/2026: Whitewater and the top 10 Japan resorts (each resort's own pages, read in a browser) ----------
_D = "2026-11-20"
_WW = "https://whitewatermountainresort.com"
_NU = "https://www.niseko.ne.jp/en/wp-content/uploads/2026/09/2026-27_NU_Trail-Map_"
_HAPPO = "https://www.happo-one.jp/wp2019/wp-content/themes/happo-one2020/img/info/pamphlet/eng2025-2026/"
IKON_ACCESS.update({s: _IKON_7 for s in ("niseko", "furano", "shiga-kogen", "lotte-arai", "zao-onsen", "appi")})
CURATED.update({
    "whitewater": {
        "opening_day": _c("2026-12-04", _WW + "/hours-operation", "Whitewater: Hours of Operation", note="Tentative.", checked=_D),
        "closing_day": _c("2027-04-04", _WW + "/hours-operation", "Whitewater: Hours of Operation", checked=_D),
        "lift_hours": _c("Silver King and Raven chairs 9:30 AM to 4 PM, Summit Chair to 3:30 PM, Hummer Handle Tow to 3:50 PM. "
                         "Glory Chair opens when the snowpack permits.", _WW + "/hours-operation", "Whitewater: Hours of Operation", checked=_D),
        "trail_map": dict(_map(_WW + "/trail-maps", "Whitewater: Trail Maps",
                               "2026/27 trail map with terrain close-ups, Short Side and Nordic maps (on whitewatermountainresort.com)", [
                                   ("Trail map", "2026/27", _WW + "/site/assets/files/4827/trail_map_inside_2026_2027_rgb.png", None),
                                   ("Resort overview and Raven terrain", "2026/27", _WW + "/site/assets/files/9997/trail_map_inside_2026_2027_-_resort_overview_raven_terrain.1350x760p50x50.webp", None),
                                   ("Summit and Glory terrain", "2026/27", _WW + "/site/assets/files/9967/trail_map_inside_2026_2027_-_summit_terrain_glory_terrain.1350x760p50x50.webp", None),
                                   ("Short Side", "2026/27", _WW + "/site/assets/files/21449/short_side_trail_map_2026_2027_for_website_card_display.600x689p50x50.webp", None),
                                   ("Nordic trails", "2024/25", None, _WW + "/site/assets/files/2226/nordic_trail_map_2024_2025_rgb.pdf")]), checked=_D),
    },
    "niseko": {
        "opening_day": _c("2026-11-28", "https://en.grand-hirafu.jp/snow/", "Niseko Tokyu Grand Hirafu: Snow",
                          note="Grand Hirafu's scheduled season; Annupuri, Niseko Village and Hanazono set their own dates.", checked=_D),
        "closing_day": _c("2027-05-05", "https://en.grand-hirafu.jp/snow/", "Niseko Tokyu Grand Hirafu: Snow", note="Grand Hirafu, scheduled.", checked=_D),
        "trail_map": dict(_map("https://www.niseko.ne.jp/en/map/", "Niseko United: Trail Map",
                               "2026/27 Niseko United map plus Annupuri, Grand Hirafu and Hanazono maps (on niseko.ne.jp)", [
                                   ("Niseko United, all four resorts", "2026/27", _NU + "EN-scaled.jpg",
                                    "https://www.niseko.ne.jp/ja/wp-content/uploads/2020/08/2026-27_NU_Trail-Map_EN.pdf"),
                                   ("Annupuri", "2026/27", _NU + "Annupuri_EN-scaled.jpg", None),
                                   ("Grand Hirafu", "2026/27", _NU + "NisekoTokyuGrandHirafu_EN-1-scaled.jpg", None),
                                   ("Hanazono", "2026/27", _NU + "HANAZONO_EN-scaled.jpg", None)]), checked=_D),
    },
    "rusutsu": {
        "opening_day": _c("2026-11-28", "https://rusutsu.com/en/winter-lift-tickets/", "Rusutsu: Winter Lift Tickets", note="Scheduled.", checked=_D),
        "closing_day": _c("2027-03-31", "https://rusutsu.com/en/winter-lift-tickets/", "Rusutsu: Winter Lift Tickets", note="End of spring season.", checked=_D),
        "lift_hours": _c("Night skiing 4 PM to 8 PM (last ride 7:45 PM) from mid-December to 3/30. Ticket counters open 8:15 AM.",
                         "https://rusutsu.com/en/winter-lift-tickets/", "Rusutsu: Winter Lift Tickets", checked=_D),
        "trail_map": dict(_map("https://rusutsu.com/en/trail-map/", "Rusutsu: Trail Map", "Winter trail map (on rusutsu.com)", [
            ("Winter trail map", "Current winter", "https://rusutsu.com/wp-content/uploads/trail-map-winter_en-1.jpg",
             "https://rusutsu.com/wp-content/uploads/trailmap_en-1.pdf")]), checked=_D),
        "passes": _c("Epic Pass, Epic Local Pass and Epic Australia Pass: 5 unrestricted, consecutive days.", "https://rusutsu.com/en/epic-pass/",
                     "Rusutsu: Epic Pass", note="Rusutsu's page still names the 2025-26 season.", checked=_D,
                     rows=[("Epic Pass", "5 consecutive days, unrestricted"), ("Epic Local Pass", "5 consecutive days, unrestricted"),
                           ("Epic Australia Pass", "5 consecutive days, unrestricted")]),
    },
    "furano": {
        "opening_day": _c("2026-11-28", "https://furapuri.com/ski/", "Furano Ski Resort Snow Report", note="Scheduled.", checked=_D),
        "lift_hours": _c("Furano Ropeway 9 AM to 4 PM.", "https://furapuri.com/ski/", "Furano Ski Resort Snow Report", checked=_D),
        "trail_map": dict(_map("https://www.princehotels.com/en/ski/furano/", "Furano: Prince Snow Resorts", "Mountain map (on princehotels.com)", [
            ("Mountain map", "Current winter", "https://www.princehotels.com/en/ski/furano/mountain_map.jpg", None)]), checked=_D),
    },
    "kiroro": {
        "opening_day": _c("2026-11-28", "https://www.kiroro.co.jp/en/operating_hours/", "Kiroro: Operating Hours", checked=_D),
        "lift_hours": _c("Early season (11/28 to 12/11): most lifts 9 AM to 3:30 PM; Gateway Express (gondola cabins) 8:30 AM to 4:15 PM.",
                         "https://www.kiroro.co.jp/en/operating_hours/", "Kiroro: Operating Hours", checked=_D),
        "trail_map": dict(_map("https://www.kiroro.co.jp/guide_map/", "Kiroro: Guide Map", "Guide map (on kiroro.co.jp)", [
            ("Guide map", "2026", "https://www.kiroro.co.jp/wp-content/uploads/2026/10/map_260730_en-002.jpg", None)]), checked=_D),
    },
    "hakuba-happo-one": {
        "opening_day": _c("2026-12-01", "https://www.happo-one.jp/en/ticket/", "Hakuba Happo-one: Tickets & Passes",
                          note="Early-season lift tickets start 12/1; the opening day itself depends on snow.", checked=_D),
        "closing_day": _c("2027-05-05", "https://www.happo-one.jp/en/ticket/", "Hakuba Happo-one: Tickets & Passes", note="End of the spring ticket season.", checked=_D),
        "trail_map": dict(_map("https://www.happo-one.jp/en/gelande/", "Hakuba Happo-one: The Mountain", "Course map and course guide (2025/26 English file, on happo-one.jp)", [
            ("Course map", "2025/26", _HAPPO + "course_guide.jpg", _HAPPO + "course_map.pdf")]), checked=_D),
    },
    "nozawa-onsen": {
        "opening_day": _c("2026-11-28", "https://nozawaski.com/winter/course/", "Nozawa Onsen Ski Resort: Slope conditions (Japanese)", note="Scheduled.", checked=_D),
        "closing_day": _c("2027-05-05", "https://nozawaski.com/winter/lift_price/lift_time/", "Nozawa Onsen Ski Resort: Lift hours (Japanese)",
                          note="Spring lift schedule runs to 5/5.", checked=_D),
        "lift_hours": _c("Nagasaka Gondola 8:30 AM to 3:30 PM (11/29 to 3/28), 8:10 AM to 3 PM in spring. Night skiing on the Nagasaka Four lift "
                         "4:30 to 8 PM over New Year and on Saturdays from 1/9 to 3/20.", "https://nozawaski.com/winter/lift_price/lift_time/",
                         "Nozawa Onsen Ski Resort: Lift hours (Japanese)", checked=_D),
        "trail_map": dict(_map("https://nozawaski.com/winter/course/map/", "Nozawa Onsen Ski Resort: Slope map (Japanese)", "Slope map (on nozawaski.com)", [
            ("Slope map", "2026", "https://nozawaski.com/cms/wp-content/themes/nozawa-ski/assets/img/gelande/gelandemap_base2026.png", None)]), checked=_D),
    },
    "shiga-kogen": {
        "opening_day": _c("2026-11-21", "https://www.shigakogen.gr.jp/english/topics/shigakogen-ski-infomation.html", "Shiga Kogen: 26-27 Ski Resort Information",
                          note="Yokoteyama first. Kumanoyu late November, Yakebitaiyama 12/4, Central 12/5 (partly), Okushiga Kogen 12/12.", checked=_D),
        "trail_map": _c("https://www.shigakogen.gr.jp/english/topics/shigakogen-ski-infomation.html",
                        "https://www.shigakogen.gr.jp/english/topics/shigakogen-ski-infomation.html", "Shiga Kogen: 26-27 Ski Resort Information",
                        label="Ski area map and the SHIGA KOGEN NAVIGATOR digital map (on shigakogen.gr.jp)", checked=_D),
    },
    "lotte-arai": {
        "opening_day": _c("2026-12-12", "https://www.lottehotel.com/arai-resort/en/snow/slopes-map", "Lotte Arai: Slope map", note="Tentative.", checked=_D),
        "closing_day": _c("2027-05-09", "https://www.lottehotel.com/arai-resort/en/snow/slopes-map", "Lotte Arai: Slope map", note="Tentative.", checked=_D),
        "lift_hours": _c("8:30 AM to 4 PM (varies by lift). Night skiing 5:30 to 10 PM on Fridays and Saturdays, 12/25 to 3/20.",
                         "https://www.lottehotel.com/arai-resort/en/snow/slopes-map", "Lotte Arai: Slope map", checked=_D),
        "trail_map": dict(_map("https://www.lottehotel.com/arai-resort/en/snow/slopes-map", "Lotte Arai: Slope map", "Slope map (on lottehotel.com)", [
            ("Slope map", "Current winter", None, "https://www.lottehotel.com/cms/asset/2026/01/17/36063/%E3%82%B3%E3%83%BC%E3%82%B9%E3%83%9E%E3%83%83%E3%83%972.pdf")]), checked=_D),
    },
    "zao-onsen": {
        "trail_map": dict(_map("https://www.zao-spa.or.jp/english/ski/", "Zao Onsen Ski Resort: Ski", "Ski area map (on zao-spa.or.jp)", [
            ("Ski area map", "Current winter", "https://www.zao-spa.or.jp/english/ski/images/large_map.jpg", None)]), checked=_D),
    },
    "appi": {
        "opening_day": _c("2026-12-05", "https://www.appi.co.jp/snow-mountain-resort/course/", "APPI: Course guide (Japanese)", checked=_D),
        "closing_day": _c("2027-05-05", "https://www.appi.co.jp/snow-mountain-resort/course/", "APPI: Course guide (Japanese)",
                          note="At the latest, depending on snow.", checked=_D),
        "lift_hours": _c("8:30 AM to 4 PM.", "https://www.appi.co.jp/event/appi-winter2026-openning-event/", "APPI: Winter opening event (Japanese)", checked=_D),
        "trail_map": dict(_map("https://www.appi.co.jp/snow-mountain-resort/course/", "APPI: Course guide (Japanese)", "2026-27 course map (on appi.co.jp)", [
            ("Course map", "2026/27", "https://www.appi.co.jp/snow-mountain-resort/assets/img/course/course_2026-27_all.jpg", None)]), checked=_D),
    },
})

# Checked and not posted yet: the page says so, so the guide shows "Not posted" with the reason.
_NOT_POSTED = {
    "lift_hours": {
        "kirkwood": ("https://www.kirkwood.com" + _VR, "Kirkwood: Hours of Operation", "Kirkwood hasn't posted 2026/27 lift hours. It plans to open 12/4."),
        "stevens-pass": ("https://www.stevenspass.com" + _VR, "Stevens Pass: Hours of Operation", "Stevens Pass lists day and night lift hours as TBD."),
        "stowe": ("https://www.stowe.com" + _VR, "Stowe: Hours of Operation", "Stowe's hours page still shows summer hours; opening dates are TBD."),
        "okemo": ("https://www.okemo.com" + _VR, "Okemo: Hours of Operation", "Okemo says ski lift hours are coming soon."),
        "seven-springs": ("https://www.7springs.com" + _VR, "Seven Springs: Hours of Operation", "Seven Springs says slope hours will be posted soon."),
        "mt-bachelor": ("https://www.mtbachelor.com/the-mountain/hours-of-operation/", "Mt. Bachelor: Hours of Operation", "Mt. Bachelor says full winter 26/27 hours are coming soon. It plans to open 12/4."),
        "palisades-tahoe": ("https://www.palisadestahoe.com/mountain-information/hours-of-operation", "Palisades Tahoe: Hours of Operation", "Palisades Tahoe hasn't posted winter lift hours. It opens 11/21."),
        "crystal-mountain": ("https://www.crystalmountainresort.com/about/hours-of-operations", "Crystal Mountain: Hours of Operation", "Crystal says winter hours are coming soon."),
        "sugarbush": ("https://www.sugarbush.com/mountain/hours", "Sugarbush: Hours", "Sugarbush's hours page still shows summer hours."),
        "tremblant": ("https://www.tremblant.ca/mountain-village/opening-hours", "Tremblant: Opening Hours", "Tremblant lists season dates but points to the Ikon app for lift hours."),
        "sunday-river": ("https://www.sundayriver.com/hours-of-operation", "Sunday River: Hours of Operation", "Sunday River's hours page still shows the 2025/26 schedule (9 AM to 4 PM weekdays, 8 AM to 4 PM weekends)."),
        "grand-targhee": ("https://www.grandtarghee.com/the-mountain/cams-conditions/hours-of-operation", "Grand Targhee: Hours of Operation", "Grand Targhee hasn't posted winter lift hours."),
        "jay-peak": ("https://jaypeakresort.com/resort/hours-operation", "Jay Peak: Hours of Operation", "Jay Peak hasn't posted 2026/27 lift hours."),
        "saddleback": ("https://www.saddlebackmaine.com/hours-of-operation/", "Saddleback: Hours of Operation", "Saddleback hasn't posted lift hours. It opens 12/4."),
        "cannon": ("https://www.cannonmt.com/hours", "Cannon: Hours of Operation", "Cannon hasn't posted lift or tram hours yet."),
        "waterville-valley": ("https://www.waterville.com/hours-of-operation", "Waterville Valley: Hours of Operation", "Waterville Valley hasn't posted lift hours. It opens 11/28."),
        "mt-baker": ("https://www.mtbaker.us/the-mountain/operations-hours/", "Mt. Baker: Operations Schedule", "Mt. Baker sets days and hours by conditions and posts them as a calendar image."),
    },
    "opening_day": {
        "loon": ("https://www.loonmtn.com/hours", "Loon: Hours", "Loon says \"Opening Day TBD.\" It usually opens mid-November."),
        "big-bear": ("https://www.bigbearmountainresort.com/hours", "Big Bear: Hours", "Big Bear hasn't confirmed opening day. 11/26 is the earliest date it may open."),
        "grand-targhee": ("https://www.grandtarghee.com", "Grand Targhee: Home", "Grand Targhee planned 11/20 but is delaying opening day and hasn't set a new date."),
        "cannon": ("https://www.cannonmt.com/hours", "Cannon: Hours of Operation", "Cannon hasn't announced 26/27 opening day."),
        "seven-springs": ("https://www.7springs.com" + _VR, "Seven Springs: Hours of Operation", "Seven Springs hasn't announced opening day."),
        "mad-river-glen": ("https://www.madriverglen.com/hours/", "Mad River Glen: Hours of Operation", "Mad River Glen usually opens the second Saturday in December, snow permitting."),
    },
}
for _kind, _rows in _NOT_POSTED.items():
    for _slug, (_url, _page, _note) in _rows.items():
        CURATED.setdefault(_slug, {}).setdefault(_kind, _c(None, _url, _page, note=_note))
for _slug in ("loon", "big-bear", "grand-targhee", "cannon", "seven-springs", "mad-river-glen"):
    _o = CURATED[_slug]["opening_day"]
    CURATED[_slug].setdefault("closing_day", _c(None, _o["source"], _o["source_name"], note="Not announced."))
CURATED.setdefault("jackson-hole", {})["lift_tickets"] = _c(
    "From $85 online for a 1-day adult ticket on select dates.", "https://www.jacksonhole.com/lift-tickets", "Jackson Hole: Lift Tickets",
    note="The best rates are tiered and sold in limited numbers. Buying earlier, booking 3+ days and skiing non-peak dates save the most.")
CURATED.setdefault("big-sky", {})["lift_tickets"] = _c(
    None, "https://www.bigskyresort.com/winter-tickets/lift-ticket", "Big Sky: Lift Tickets",
    note="Big Sky doesn't list a fixed 1-day price. Booking ahead gets the lowest price, multi-day tickets cost less per day, and kids 6 and under ski for $1 a day.")


def _fact(value, src, **extra):
    return dict({"value": value, "checked": CHECKED_SHARED, "source": src[0], "source_name": src[1]}, **extra)


def _shared(slug, name):
    out = {}
    if slug in ANNOUNCED:
        o, c, src = ANNOUNCED[slug]
        out["opening_day"] = _fact(o, src)
        out["closing_day"] = _fact(c, src)
    if slug == "telluride":
        out["lift_hours"] = _fact(TELLURIDE_HOURS, ANNOUNCED["telluride"][2])
    if slug in LIFT_HOURS:
        value, src = LIFT_HOURS[slug]
        out["lift_hours"] = _fact(value, src)
    if slug in TRAIL_MAPS:
        url, label = TRAIL_MAPS[slug]
        out["trail_map"] = _fact(url, (url, f"{name}: Trail and Mountain Maps"), label=label)
    if slug in EPIC_ACCESS:
        full, local = EPIC_ACCESS[slug]
        text = f"Epic Pass: {full}. " + (f"Epic Local Pass: {local}. " if local else f"The Epic Local Pass doesn't include {name}. ")
        text += "Epic Day Pass: not valid on peak dates."
        rows = [("Epic Pass", full), ("Epic Local Pass", local or "Not included"), ("Epic Day Pass", "Not valid on peak dates")]
        out["passes"] = _fact(text, EPIC_LOCAL if local else EPIC_PASS, rows=rows)
        on_peak = [p for p, rule in (("Epic Local Pass", local),) if rule and "not valid on peak" in rule]
        applies = " and ".join(on_peak + ["Epic Day Pass"])
        out["blackout_dates"] = _fact(f"{EPIC_PEAK_DATES}. These apply to the {applies}"
                                      + (". The full Epic Pass has none." if "unlimited" in full else "."), EPIC_PEAK,
                                      pass_key="epic-blackout-dates", applies=applies)
    if slug in IKON_ACCESS:
        full, base, session = IKON_ACCESS[slug]
        bits = [f"Ikon Pass: {full}" + (", no blackout dates" if full == "unlimited" else "")]
        bits.append(f"Ikon Base Pass: {base}" + (", with blackout dates" if base else "") if base else f"The Ikon Base Pass doesn't include {name}")
        if session:
            bits.append(f"Ikon Session Pass: {session}")
        rows = [("Ikon Pass", full + (", no blackout dates" if full == "unlimited" else "")),
                ("Ikon Base Pass", (base + ", with blackout dates") if base else "Not included")]
        if session:
            rows.append(("Ikon Session Pass", session))
        out["passes"] = _fact(". ".join(bits) + ".", IKON_COMPARE, rows=rows)
        out["blackout_dates"] = (_fact(f"{IKON_BASE_DATES} on the Ikon Base Pass. The full Ikon Pass has none.", IKON_BASE_BLACKOUTS,
                                       pass_key="ikon-blackout-dates", applies="Ikon Base Pass") if base
                                 else _fact(f"None. The Ikon Pass has no blackout dates, and the Ikon Base Pass doesn't include {name}.",
                                            IKON_COMPARE, pass_key=None, applies=None))
    return out


def _build():
    from . import resorts
    out = {}
    for slug in resorts.RESORTS:
        name = resorts.RESORTS[slug]["name"]
        shared = _shared(slug, name)
        merged = dict(shared, **CURATED.get(slug, {}))
        # Hand-checked pass facts keep the structured rows and blackout ranges from the shared tables.
        for kind, keys in (("passes", ("rows",)), ("blackout_dates", ("pass_key", "applies"))):
            if kind in CURATED.get(slug, {}) and kind in shared and shared[kind]["source"] == merged[kind]["source"]:
                merged[kind] = dict({k: shared[kind][k] for k in keys if k in shared[kind]}, **merged[kind])
        if merged:
            out[slug] = merged
    return out


FACTS = _build()

LABELS = {"opening_day": "Opening day", "closing_day": "Closing day", "lift_hours": "Lift hours", "trail_map": "Trail map",
          "passes": "Passes", "blackout_dates": "Blackout dates", "lift_tickets": "Lift tickets", "lessons": "Lessons"}


SHORT = {"opening_day": "opening day", "closing_day": "closing day", "lift_hours": "lift hours", "trail_map": "trail map",
         "passes": "passes", "blackout_dates": "blackout dates", "lift_tickets": "lift ticket prices", "lessons": "lessons"}


def topics(slug):
    """What a resort's guide covers, in page order, e.g. "opening day, closing day, passes and blackout dates"."""
    have = [SHORT[k] for k in LABELS if k in (FACTS.get(slug) or {})]
    return ", ".join(have[:-1]) + (" and " if len(have) > 1 else "") + (have[-1] if have else "")


# ---------- adding a resort: where to look ----------
# Each operator lays its sites out the same way, so one checked path pattern covers all its resorts.
# Paths were confirmed on beavercreek.com (Vail Resorts). Read the page before trusting a fact: the
# path only says where to look. See docs/RESORT_FACTS.md.
OPERATOR_PAGES = {
    "vail-resorts": {
        "lift_hours": "/explore-the-resort/about-the-resort/hours-of-operation.aspx",
        "trail_map": "/the-mountain/about-the-mountain/trail-map.aspx",
        "lift_tickets": "/plan-your-trip/lift-access/tickets.aspx",
        "lessons": "/plan-your-trip/ski-and-ride-lessons.aspx",
    },
}
OPERATOR = {s: "vail-resorts" for s in ("beaver-creek", "vail", "breckenridge", "keystone", "crested-butte", "park-city",
                                        "whistler-blackcomb", "heavenly", "northstar", "kirkwood", "stevens-pass", "stowe",
                                        "okemo", "mount-snow", "seven-springs")}


def missing(slug):
    """Fact kinds a resort's guide doesn't have yet."""
    have = FACTS.get(slug) or {}
    return [k for k in LABELS if k not in have]


def todo():
    """[(slug, kind, where to read it)] for every missing fact, so the next person knows what to check."""
    from . import resorts
    out = []
    for slug, r in resorts.RESORTS.items():
        pages = OPERATOR_PAGES.get(OPERATOR.get(slug), {})
        for kind in missing(slug):
            where = r["site"] + pages[kind] if kind in pages else f'{r["site"]} (find the official page)'
            out.append((slug, kind, where))
    return out


def _in(today, start, end):
    """Is today between two (month, day) points, inclusive? Handles ranges that cross New Year."""
    t = (today.month, today.day)
    return start <= t <= end if start <= end else (t >= start or t <= end)


def interval_days(kind, today):
    """How often a fact is re-checked, by season. Busy weeks get checked every 2 days."""
    if kind == "closing_day":
        return 2 if _in(today, (3, 1), (5, 31)) else 30
    if kind == "opening_day":
        return 2 if _in(today, (9, 15), (11, 30)) else 30
    if kind == "lift_hours":
        return 7 if _in(today, (11, 1), (4, 30)) else 30
    if kind == "trail_map":
        return 7 if _in(today, (10, 15), (12, 15)) else 30
    if kind in ("passes", "blackout_dates"):
        # Next season's passes and their blackout dates are announced and go on sale in March.
        return 2 if _in(today, (3, 1), (4, 30)) else 30
    if kind == "lift_tickets":
        return 7 if _in(today, (11, 1), (4, 30)) else 30
    if kind == "lessons":
        return 14 if _in(today, (10, 1), (12, 31)) else 30
    return 30


def due(today=None, facts=None):
    """Facts whose next check date has come: [(slug, kind, days overdue)], most overdue first."""
    today = today or date.today()
    out = []
    for slug, kinds in (facts or FACTS).items():
        for kind, f in kinds.items():
            nxt = date.fromisoformat(f["checked"]) + timedelta(days=interval_days(kind, today))
            if today >= nxt:
                out.append((slug, kind, (today - nxt).days))
    return sorted(out, key=lambda x: -x[2])


def stale(f, kind, today=None):
    """Shown on the page when a fact is more than twice its check interval old."""
    today = today or date.today()
    return (today - date.fromisoformat(f["checked"])).days > 2 * interval_days(kind, today)


# ---------- page watch ----------

KEY_LINE = re.compile(r"(open|clos|hours|season|\b\d{1,2}(:\d\d)?\s?(am|pm)\b|\b\d{1,2}/\d{1,2}\b|"
                      r"january|february|march|april|may|june|november|december)", re.I)


# Bot walls and empty JavaScript shells come back as a 200 but carry none of the page: treat them as a failed read.
BLOCKED = re.compile(r"(just a moment\.\.\.|cf-chl|challenge-platform|captcha|access denied|attention required|"
                     r"enable javascript to|request unsuccessful|incapsula|are you a robot)", re.I)
MAX_LINES = 60  # key lines kept per page for the re-check diff


def key_lines(page_html):
    """The page's lines that carry dates and hours, sorted, without menus, scripts or promos."""
    text = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", page_html or "")
    text = html.unescape(re.sub(r"(?s)<[^>]+>", "\n", text))
    return sorted({ln.strip() for ln in text.splitlines() if ln.strip() and len(ln.strip()) < 300 and KEY_LINE.search(ln)})


def fingerprint(page_html):
    """Hash only the lines that carry dates and hours, so menus and promos don't trip it."""
    return hashlib.sha256("\n".join(key_lines(page_html)).encode()).hexdigest()[:16]


def blocked(page_html):
    """A read that didn't get the real page: a bot wall, a challenge, or a shell with no dates or hours at all."""
    return not key_lines(page_html) or bool(BLOCKED.search((page_html or "")[:20000]))


def watch(store, fetch, now=None):
    """Read every source page once and write data/facts/status.json. `fetch(url) -> html or None`.

    A page counts as changed only when the new text is still there on the next read (one-off promos,
    countdowns and A/B tests don't flag it). Bot walls and empty shells count as errors, not changes.
    The status carries a work queue for the re-check task: every fact that is due, plus every fact
    whose source changed, with the lines that were added and removed. Returns the status written."""
    now = now or datetime.now()
    stamp = now.isoformat(timespec="minutes")
    prev = store.get_json("data/facts/status.json", {}) or {}
    seen = dict(prev.get("pages") or {})
    changed, failing = [], []
    urls = sorted({f["source"] for kinds in FACTS.values() for f in kinds.values()})
    # 170+ pages won't fit a 60 s function one at a time: read them in parallel.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=32) as pool:
        pages = dict(zip(urls, pool.map(fetch, urls)))
    for url in urls:
        page = pages[url]
        entry = dict(seen.get(url) or {})
        if page is None or blocked(page):
            entry["error_at"] = stamp
            entry["errors"] = entry.get("errors", 0) + 1
            entry["error"] = "no response" if page is None else "blocked or empty page"
            if entry["errors"] >= 3:
                failing.append(url)
            seen[url] = entry
            continue
        lines = key_lines(page)[:MAX_LINES]
        fp = fingerprint(page)
        entry.update(read_at=stamp, errors=0)
        entry.pop("error", None)
        if not entry.get("fp"):
            entry.update(fp=fp, lines=lines)
        elif fp == entry["fp"]:
            entry.pop("pending_fp", None)
            entry["lines"] = lines
        elif entry.get("pending_fp") == fp:  # second read in a row with the new text: a real change
            entry.update(prev_lines=entry.get("lines") or [], lines=lines, fp=fp, changed_at=stamp)
            entry.pop("pending_fp", None)
            changed.append(url)
        else:
            entry["pending_fp"] = fp
        seen[url] = entry
    # A change stays in the queue until the facts on that page are re-checked after it.
    queue = []
    due_now = {(s, k): d for s, k, d in due(now.date())}
    for slug, kinds in FACTS.items():
        for kind, f in kinds.items():
            page = seen.get(f["source"]) or {}
            moved = page.get("changed_at") and page["changed_at"][:10] > f["checked"]
            if not moved and (slug, kind) not in due_now:
                continue
            item = {"resort": slug, "fact": kind, "source": f["source"], "value": f.get("value"),
                    "checked": f["checked"], "reason": "changed" if moved else "due",
                    "overdue_days": due_now.get((slug, kind), 0)}
            if moved:
                old, new = set(page.get("prev_lines") or []), set(page.get("lines") or [])
                item.update(changed_at=page["changed_at"], added=sorted(new - old)[:10], removed=sorted(old - new)[:10])
            queue.append(item)
    queue.sort(key=lambda q: (q["reason"] != "changed", -q["overdue_days"], q["resort"], q["fact"]))
    status = {"generated": stamp, "pages": seen, "changed_today": changed, "failing": failing,
              "due": [{"resort": s, "fact": k, "overdue_days": d} for (s, k), d in due_now.items()], "queue": queue}
    store.put_json("data/facts/status.json", status)
    return status


if __name__ == "__main__":  # python -m bcbot.facts [todo|due]
    import sys
    if (sys.argv[1:] or ["todo"])[0] == "due":
        for slug, kind, late in due():
            print(f"{slug:16} {kind:15} {late} days overdue")
    else:
        rows = todo()
        for slug, kind, where in rows:
            print(f"{slug:16} {kind:15} {where}")
        print(f"\n{len(rows)} missing facts across {len({r[0] for r in rows})} resorts")


# ---------- owner view: what we have, what's missing, how fresh (/admin "Resort facts") ----------

def grid(today=None):
    """One row per resort and fact kind for the private admin table and its CSV export.
    status: "filled" (a value), "not_posted" (we checked and the resort hasn't posted it), "missing" (never checked).
    fresh: "ok", "due" (next check date has come) or "stale" (more than twice the check interval old)."""
    from . import resorts
    today = today or date.today()
    rows = []
    for slug, r in resorts.RESORTS.items():
        have = FACTS.get(slug) or {}
        for kind in LABELS:
            f = have.get(kind)
            row = {"resort": slug, "name": r["name"], "fact": kind, "label": LABELS[kind],
                   "stage": "live" if r["enabled"] else r.get("stage", "off")}
            if not f:
                rows.append(dict(row, status="missing", fresh="", value="", checked="", next_check="",
                                 source="", source_name="", maps=0, map_images=0))
                continue
            every = interval_days(kind, today)
            nxt = date.fromisoformat(f["checked"]) + timedelta(days=every)
            value = f.get("value")
            if kind == "trail_map":
                value = f.get("label") or value
            rows.append(dict(
                row, status="filled" if f.get("value") else "not_posted",
                fresh="stale" if stale(f, kind, today) else "due" if today >= nxt else "ok",
                value=value or f.get("note") or "", checked=f["checked"], next_check=nxt.isoformat(), every_days=every,
                source=f["source"], source_name=f.get("source_name", ""),
                maps=len(f.get("maps") or []), map_images=sum(1 for m in f.get("maps") or [] if m.get("image"))))
    return {"today": today.isoformat(), "kinds": list(LABELS), "labels": LABELS, "rows": rows}
