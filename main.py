from logging import getLogger, INFO
from math import ceil
from os import getenv

from discord import Activity, ActivityType, Embed
from discord.ext import commands, menus
from discord.ext.menus.views import ViewMenuPages
from dotenv import load_dotenv

import peoplesoft as ps

# Suppress debug-level logging messages from discord.py
getLogger("discord").setLevel(INFO)
getLogger("urllib3").setLevel(INFO)

load_dotenv()
DISCORD_TOKEN = getenv("DISCORD_TOKEN")
PREFIX = "?"
bot = commands.Bot(command_prefix=PREFIX)

ZERO_WIDTH_SPACE = "\u200b"
PITT_ROYAL = 0x003594
PITT_GOLD = 0xFFB81C


class EmbedPages(menus.ListPageSource):
    """Multi-page embed class for displaying info on one embed at a time."""

    def __init__(self, data):
        super().__init__(data, per_page=1)

    async def format_page(self, menu, entry: Embed) -> Embed:
        return entry


class SubjectPages(menus.ListPageSource):
    """Multi-page embed class for displaying lists of subjects in columns."""

    def __init__(self, data, campus):
        super().__init__(data, per_page=12)
        self.pages = ceil(len(self.entries) / self.per_page)
        self.campus = campus

    async def format_page(self, menu, entries: list[ps.SubjectCode]) -> Embed:
        page = Embed(title=f"SUBJECTS OFFERED AT {self.campus.upper()} CAMPUS",
                     color=PITT_GOLD if menu.current_page % 2 else PITT_ROYAL)
        for subject in entries:
            page.add_field(name=subject.subject_code, value=subject.desc)
        for _ in range((3 - (len(entries) % 3)) % 3):
            # Empty fields serve as placeholders for alignment
            page.add_field(name=ZERO_WIDTH_SPACE, value=ZERO_WIDTH_SPACE)
        page.set_footer(text=f"Page {menu.current_page + 1} of {self.pages}")
        return page


@bot.event
async def on_ready():
    await bot.change_presence(
        activity=Activity(type=ActivityType.watching, name=f"for {PREFIX}help"))
    print(f"PeopleSoft Bot is now running on {len(bot.guilds)} "
          f"server{'s' if len(bot.guilds) > 1 else ''}:")
    for guild in bot.guilds:
        print(f"{guild.name}\t{guild.id}")


@bot.command(description="pong")
async def ping(ctx):
    """Simple ping-pong command to test client connection."""
    await ctx.send("pong")


@bot.command(description="Gets list of subjects for one of Pitt's campuses")
async def subjects(ctx, *args):
    """Get and displays a multi-page embed of the list of subjects for one of
    Pitt's campuses. Campus is assumed to be main campus unless specified
    otherwise."""
    params = {}
    campus = "main"
    match [arg.lower() for arg in args]:
        case [arg, *_] if arg in ps.CAMPUSES:  # ?subjects [campus] ...
            params["campus"] = ps.CAMPUSES[arg]
            campus = arg
        case []:  # ?subjects
            pass
        case _:  # ?subjects [not-a-campus] ...
            await handle_error(ctx, ValueError("Invalid campus"))
    try:
        subject_info = ps.get_detailed_subject_codes(**params)
        pages = ViewMenuPages(
            source=SubjectPages(data=subject_info, campus=campus))
        await pages.start(ctx)
    except Exception as e:
        await handle_error(ctx, e)


@bot.command(description="Gets info about sections for a specific course")
async def course(ctx, *args):
    def format_course(info: ps.Course) -> list[Embed]:
        embeds = []
        for i, sct in enumerate(info.sections, start=1):
            embed = Embed(title=f"{info.subject_code} {info.course_num}: "
                                f"{info.course_title}",
                          color=PITT_ROYAL if i % 2 else PITT_GOLD)
            embed.add_field(name="Type", value=sct.section_type)
            embed.add_field(name="Section #", value=sct.section_num)
            embed.add_field(name="Class #", value=sct.class_num)

            embed.add_field(name="Instructor", value=sct.instructor)
            embed.add_field(name="Location", value=sct.room)
            # Empty fields serve as placeholders for alignment
            embed.add_field(name=ZERO_WIDTH_SPACE, value=ZERO_WIDTH_SPACE)

            embed.add_field(name="Days/Times", value=sct.days_times)
            embed.add_field(name="Dates", value=sct.dates)
            # Empty fields serve as placeholders for alignment
            embed.add_field(name=ZERO_WIDTH_SPACE, value=ZERO_WIDTH_SPACE)

            embed.add_field(name="Status", value=sct.status)
            if sct.waitlist_size is not None:
                embed.add_field(name="Waitlist Size", value=sct.waitlist_size)
                # Empty fields serve as placeholders for alignment
                embed.add_field(name=ZERO_WIDTH_SPACE, value=ZERO_WIDTH_SPACE)
            embed.set_footer(text=f"Page {i} of {len(info.sections)}")
            embeds.append(embed)
        return embeds

    match [arg.lower() for arg in args]:
        # ?course [subject] [course num] ...
        case [subject, course_num, *others]:
            params = dict(subject=subject, course=course_num)
            # Set term and campus if specified
            for other in others:
                if other in ps.TERMS:
                    params['term'] = ps.TERMS[other]
                elif other in ps.CAMPUSES:
                    params['campus'] = ps.CAMPUSES[other]
            try:
                course_info = ps.get_course(**params)
                pages = ViewMenuPages(
                    source=EmbedPages(format_course(course_info)))
                await pages.start(ctx)
            except Exception as e:
                await handle_error(ctx, e)
        case _:
            await handle_error(ctx, Exception("Incorrect command format"))


@bot.command(description="Gets info about a specific course section")
async def section(ctx, *args):
    def format_section(info: ps.SectionDetails) -> list[Embed]:
        """Helper function for formatting embeds for section info."""

        # First embed page is for enrollment info (section #, units, etc.)
        embed1 = Embed(title=f"{info.subject_code} {info.course_num}: "
                             f"{info.course_title} ({info.class_num})",
                       description=info.desc, color=PITT_ROYAL)
        embed1.add_field(name="Section #", value=info.section_num)
        embed1.add_field(name="Session", value=info.session)
        embed1.add_field(name="Units", value=info.units)

        if len(info.components) > 0:
            embed1.add_field(
                name="Components", value="\n".join(info.components))
        if info.attrs:
            embed1.add_field(name="Attributes", value="\n".join(info.attrs))
        embed1.add_field(name="Grading", value=info.grading)
        if info.prereqs:
            embed1.add_field(name="Enrollment Reqs", value=info.prereqs)
        if info.consent:
            embed1.add_field(name="Add Consent", value=info.consent)
        if info.notes:
            embed1.add_field(name="Notes", value=info.notes)

        # Second embed page is for scheduling info (instructor, days/times,
        # location, etc.)
        embed2 = Embed(title=f"{info.subject_code} {info.course_num}: "
                             f"{info.course_title} ({info.class_num})",
                       description=info.desc, color=PITT_GOLD)
        embed2.add_field(name="Instructor", value=info.instructor)
        embed2.add_field(name="Days/Times", value=info.days_times)
        embed2.add_field(name="Dates", value=info.dates)

        embed2.add_field(name="Location", value=info.room)
        embed2.add_field(name="Campus", value=info.campus)
        embed2.add_field(name="Status", value=info.status)

        # Third embed page is for capacity info (open seats, restricted seats,
        # waitlists, etc.)
        embed3 = Embed(title=f"{info.subject_code} {info.course_num}: "
                             f"{info.course_title} ({info.class_num})",
                       description=info.desc, color=PITT_ROYAL)
        embed3.add_field(name="Class Capacity", value=info.total_capacity)
        embed3.add_field(name="Seats Taken", value=info.seats_taken)
        embed3.add_field(name="Seats Open", value=info.seats_open)
        if info.seat_restrictions:
            embed3.add_field(name="Enrollment Restrictions",
                             value="\n".join(f"{label} — {n}" for label, n
                                             in info.seat_restrictions.items()))
            embed3.add_field(name="Restricted Seats Open",
                             value=info.restricted_seats)
            embed3.add_field(name="Unrestricted Seats Open",
                             value=info.unrestricted_seats)
        embed3.add_field(name="Waitlist Capacity",
                         value=info.waitlist_capacity)
        embed3.add_field(name="Waitlist Size", value=info.waitlist_size)
        # Empty fields serve as placeholders for alignment
        embed3.add_field(name=ZERO_WIDTH_SPACE, value=ZERO_WIDTH_SPACE)

        embeds = [embed1, embed2, embed3]
        for i, embed in enumerate(embeds, start=1):
            embed.set_footer(text=f"Page {i} of {len(embeds)}")
        return embeds

    match [arg.lower() for arg in args]:
        case [class_num, *others]:  # ?section [class num] ...
            params = {"class_num": class_num}
            # Set term if specified (current term is default)
            for other in others:
                if other in ps.TERMS:
                    params['term'] = ps.TERMS[other]
            try:
                sct_info = ps.get_section(**params)
                pages = ViewMenuPages(
                    source=EmbedPages(format_section(sct_info)))
                await pages.start(ctx)
            except Exception as e:
                await handle_error(ctx, e)
        case _:
            await handle_error(ctx, Exception("No class number provided"))


@subjects.error
@course.error
@section.error
async def handle_error(ctx, e: Exception) -> None:
    await ctx.send(f"**{type(e).__name__}: {e}**")


bot.run(DISCORD_TOKEN)
