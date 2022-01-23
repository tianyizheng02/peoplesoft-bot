from math import ceil
from os import getenv

from discord import Activity, ActivityType, Embed
from discord.ext import commands, menus
from discord.ext.menus.views import ViewMenuPages
from dotenv import load_dotenv

import peoplesoft as ps

load_dotenv()
DISCORD_TOKEN = getenv("DISCORD_TOKEN")
MY_ID = getenv("MY_ID")
PREFIX = "?"
bot = commands.Bot(command_prefix=PREFIX, case_insensitive=True)

ZERO_WIDTH_SPACE = "\u200b"
PITT_ROYAL = 0x003594
PITT_GOLD = 0xFFB81C

ARTICLES = {"the", "a", "an"}
CONJ = {"for", "and", "nor", "but", "or", "yet", "so"}
PREP = {"of", "to", "for", "in"}
ALL_CAPS = {"cs", "ms"}
NO_CAPS = ARTICLES.union(CONJ).union(PREP)
SPECIAL_CAPS = {"phd": "PhD"}


class EmbedPages(menus.ListPageSource):
    """Multi-page embed class for displaying info on one embed at a time."""

    def __init__(self, data):
        super().__init__(data, per_page=1)

    async def format_page(self, menu, entry: Embed) -> Embed:
        return entry


class ColumnPages(menus.ListPageSource):
    """Multi-page embed class for displaying lists of subjects in columns."""

    def __init__(self, data, title):
        super().__init__(data, per_page=12)
        self.pages = ceil(len(self.entries) / self.per_page)
        self.title = title

    async def format_page(self, menu, entries: list[tuple[str, str]]) -> Embed:
        page = Embed(title=self.title,
                     color=PITT_GOLD if menu.current_page % 2 else PITT_ROYAL)
        for heading, desc in entries:
            page.add_field(name=heading, value=desc)
        for _ in range((3 - (len(entries) % 3)) % 3):
            # Empty fields serve as placeholders for alignment
            page.add_field(name=ZERO_WIDTH_SPACE, value=ZERO_WIDTH_SPACE)
        page.set_footer(text=f"Page {menu.current_page + 1} of {self.pages}")
        return page


def titlecase(string: str) -> str:
    words = []
    for i, word in enumerate(string.lower().split()):
        if word in ALL_CAPS:
            words.append(word.upper())
        elif word in SPECIAL_CAPS:
            words.append(SPECIAL_CAPS[word])
        elif i != 0 and word in NO_CAPS:
            words.append(word)
        else:
            words.append(word.title())
    return ' '.join(words)


@bot.event
async def on_ready():
    await bot.change_presence(
        activity=Activity(type=ActivityType.watching, name=f"for {PREFIX}help"))
    print(f"PeopleSoft Bot is now running on {len(bot.guilds)} "
          f"server{'s' if len(bot.guilds) > 1 else ''}:")
    for guild in bot.guilds:
        print(f"\t{guild.name}\t{guild.id}")


@bot.command(description="pong")
async def ping(ctx):
    """Ping-pong command to test connection (creator only)."""
    if ctx.author.id == int(MY_ID):
        await ctx.send("pong")


@bot.command(description="Gets list of subjects for a specific campus")
async def subjects(ctx, *args):
    """Get and displays a multi-page embed of the list of subjects for a
    specific campus. Campus is assumed to be main campus unless specified
    otherwise."""
    params = {}
    campus = ps.MAIN_CAMPUS
    match [arg.lower() for arg in args]:
        case [arg]:
            if arg in ps.CAMPUSES:  # ?subjects [campus]
                campus = arg.capitalize()
                params["campus"] = ps.CAMPUSES[arg]
            else:
                await handle_error(ctx, ValueError("Invalid campus"))
                return
        case []:  # ?subjects
            pass
        case _:
            await handle_error(ctx, Exception("Incorrect format"))
            return
    try:
        info = ps.get_subject_names(**params)
        page_data = ColumnPages(
            data=[(subj.subject_code, subj.desc) for subj in info],
            title=f"Subjects Available at {campus.capitalize()} Campus"
        )
        await ViewMenuPages(source=page_data).start(ctx)
    except Exception as e:
        await handle_error(ctx, e)


@bot.command(description="Gets a list of courses for a specific subject")
async def courses(ctx, *args):
    """Get and displays a multi-page embed of the list of courses for a subject.
    Term is assumed to be the current term, campus is assumed to be main campus,
    and career is assumed to be undergrad unless specified otherwise."""
    params = {}
    campus = ps.MAIN_CAMPUS
    match [arg.lower() for arg in args]:
        case [subject, *others]:  # ?courses [subject] ...
            params["subject"] = subject
            match others:
                case [arg] if arg in ps.TERMS:  # ?courses [subject] [term]
                    params["term"] = ps.TERMS[arg]
                # ?courses [subject] [campus]
                case [arg] if arg in ps.CAMPUSES:
                    campus = arg
                    params["campus"] = ps.CAMPUSES[arg]
                case [_]:  # ?courses [subject] [not a term or campus]
                    await handle_error(ctx, ValueError("Invalid term/campus"))
                    return
                # ?courses [subject] [term] [campus]
                case [arg1, arg2] if arg1 in ps.TERMS and arg2 in ps.CAMPUSES:
                    params["term"] = ps.TERMS[arg1]
                    params["campus"] = ps.CAMPUSES[arg2]
                # ?courses [subject] [term] [campus]
                case [arg1, arg2] if arg2 in ps.TERMS and arg1 in ps.CAMPUSES:
                    params["term"] = ps.TERMS[arg2]
                    params["campus"] = ps.CAMPUSES[arg1]
                # ?courses [subject] [term] [not a campus]
                case [arg, _] | [_, arg] if arg in ps.TERMS:
                    await handle_error(ctx, ValueError("Invalid campus"))
                    return
                # ?courses [subject] [campus] [not a term]
                case [arg, _] | [_, arg] if arg in ps.CAMPUSES:
                    await handle_error(ctx, ValueError("Invalid term"))
                    return
                case []:  # ?courses [subject]
                    pass
                case _:
                    await handle_error(ctx, ValueError("Incorrect format"))
                    return
        case _:
            await handle_error(ctx, Exception("No subject provided"))
            return
    try:
        info = ps.get_subject(**params)
        pages = ColumnPages(
            data=[(f"{params['subject'].upper()} {num}",
                   titlecase(course.course_title))
                  for num, course in info.courses.items()],
            title=f"{params['subject'].upper()} Courses Available at "
                  f"{campus.capitalize()} Campus"
        )
        await ViewMenuPages(source=pages).start(ctx)
    except Exception as e:
        await handle_error(ctx, e)


@bot.command(description="Gets list of sections for a specific course")
async def sections(ctx, *args):
    def format_course(course_info: ps.Course) -> list[Embed]:
        embeds = []
        for i, sct in enumerate(course_info.sections, start=1):
            embed = Embed(title=f"{course_info.subject_code} "
                                f"{course_info.course_num}: "
                                f"{titlecase(course_info.course_title)}",
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
            embed.set_footer(text=f"Page {i} of {len(course_info.sections)}")
            embeds.append(embed)
        return embeds

    match [arg.lower() for arg in args]:
        # ?sections [subject] [course num] ...
        case [subject, course_num, *others]:
            params = dict(subject=subject, course=course_num)
            # Set term and campus if specified
            match others:
                # ?sections [subject] [course num] [term]
                case [arg] if arg in ps.TERMS:
                    params["term"] = ps.TERMS[arg]
                # ?sections [subject] [course num] [campus]
                case [arg] if arg in ps.CAMPUSES:
                    params["campus"] = ps.CAMPUSES[arg]
                # ?sections [subject] [course num] [term] [campus]
                case [arg1, arg2] if arg1 in ps.TERMS and arg2 in ps.CAMPUSES:
                    params["term"] = ps.TERMS[arg1]
                    params["campus"] = ps.CAMPUSES[arg2]
                # ?sections [subject] [course num] [term] [campus]
                case [arg1, arg2] if arg2 in ps.TERMS and arg1 in ps.CAMPUSES:
                    params["term"] = ps.TERMS[arg2]
                    params["campus"] = ps.CAMPUSES[arg1]
                # ?sections [subject] [course num] [term] [not a campus]
                case [arg, _] | [_, arg] if arg in ps.TERMS:
                    await handle_error(ctx, ValueError("Invalid campus"))
                # ?sections [subject] [course num] [campus] [not a term]
                case [arg, _] | [_, arg] if arg in ps.CAMPUSES:
                    await handle_error(ctx, ValueError("Invalid term"))
                case []:  # ?sections [subject] [course num]
                    pass
                case _:
                    await handle_error(ctx, ValueError("Incorrect format"))
            try:
                info = ps.get_course(**params)
                pages = EmbedPages(format_course(info))
                await ViewMenuPages(source=pages).start(ctx)
            except Exception as e:
                await handle_error(ctx, e)
        case [_]:
            await handle_error(ctx, Exception("No course number provided"))
        case _:
            await handle_error(ctx, Exception("No subject provided"))


@bot.command(description="Gets info about a specific course section")
async def section(ctx, *args):
    def format_section(info: ps.SectionDetails) -> list[Embed]:
        """Helper function for formatting embeds for section info."""

        embed1 = Embed(title=f"{info.subject_code} {info.course_num}: "
                             f"{titlecase(info.course_title)} "
                             f"({info.class_num})",
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

        embed2 = Embed(title=f"{info.subject_code} {info.course_num}: "
                             f"{info.course_title} ({info.class_num})",
                       description=info.desc, color=PITT_GOLD)
        embed2.add_field(name="Instructor", value=info.instructor)
        embed2.add_field(name="Days/Times", value=info.days_times)
        embed2.add_field(name="Dates", value=info.dates)

        embed2.add_field(name="Location", value=info.room)
        embed2.add_field(name="Campus", value=info.campus)
        embed2.add_field(name="Status", value=info.status)

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
            match others:
                case [arg] if arg in ps.TERMS:  # ?section [class num] [term]
                    params["term"] = ps.TERMS[arg]
                case [_]:  # ?section [class num] [not a term]
                    await handle_error(ctx, ValueError("Invalid term"))
                    return
                case []:  # ?section [class num]
                    pass
                case _:
                    await handle_error(ctx, ValueError("Incorrect format"))
                    return
            try:
                sct_info = ps.get_section(**params)
                pages = EmbedPages(format_section(sct_info))
                await ViewMenuPages(source=pages).start(ctx)
            except Exception as e:
                await handle_error(ctx, e)
        case _:
            await handle_error(ctx, Exception("No class number provided"))


@subjects.error
@courses.error
@sections.error
@section.error
async def handle_error(ctx, e: Exception) -> None:
    await ctx.send(f"**{type(e).__name__}: {e}**")


bot.run(DISCORD_TOKEN)
