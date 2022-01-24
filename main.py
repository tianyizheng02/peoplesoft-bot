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
    print(f"PeopleSoft Bot is now running on {(num := len(bot.guilds))} "
          f"server{'s' if num > 1 else ''}:")
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
                params["campus"] = ps.CAMPUSES[campus := arg]
            else:
                await handle_err(ctx, ValueError("Invalid campus"))
                return
        case []:  # ?subjects
            pass
        case _:
            await handle_err(ctx, Exception("Invalid format"))
            return
    try:
        info = ps.get_subject_names(**params)
        page_data = ColumnPages(
            data=[(subj.subject_code, subj.desc) for subj in info],
            title=f"Subjects Available at {campus.capitalize()} Campus"
        )
        await ViewMenuPages(source=page_data).start(ctx)
    except Exception as e:
        await handle_err(ctx, e)


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
            match num := len(others):
                case 0:
                    pass
                case 1:
                    # ?courses [subject] [term]
                    if (arg := others[0]) in ps.TERMS:
                        params["term"] = ps.TERMS[arg]
                    elif arg in ps.CAMPUSES:  # ?courses [subject] [campus]
                        params["campus"] = ps.CAMPUSES[campus := arg]
                    else:  # ?courses [subject] [other]
                        await handle_err(ctx, ValueError("Invalid term/campus"))
                        return
                case 2:
                    for arg in others:
                        if arg in ps.TERMS:
                            params["term"] = arg
                        elif arg in ps.CAMPUSES:
                            params["campus"] = arg
                    # ?courses [subject] [term] [campus]
                    if len(params) == num + 1:
                        pass
                    # ?courses [subject] [campus] [other]
                    elif "term" not in params:
                        await handle_err(ctx, ValueError("Invalid term"))
                        return
                    # ?courses [subject] [term] [other]
                    elif "campus" not in params:
                        await handle_err(ctx, ValueError("Invalid campus"))
                        return
                    else:  # ?courses [subject] [other] [other]
                        await handle_err(ctx,
                                         ValueError("Invalid term and campus"))
                        return
                case 3:
                    for arg in others:
                        if arg in ps.TERMS:
                            params["term"] = arg
                        elif arg in ps.CAMPUSES:
                            params["campus"] = arg
                        elif arg in ps.CAREERS:
                            params["career"] = arg
                    # ?courses [subject] [term] [campus] [career]
                    if len(params) == num + 1:
                        pass
                    # ?courses [subject] [campus] [career] [other]
                    elif "term" not in params:
                        await handle_err(ctx, ValueError("Invalid term"))
                        return
                    # ?courses [subject] [term] [career] [other]
                    elif "campus" not in params:
                        await handle_err(ctx, ValueError("Invalid campus"))
                        return
                    # ?courses [subject] [term] [campus] [other]
                    elif "career" not in params:
                        await handle_err(ctx, ValueError("Invalid career"))
                        return
                    else:
                        await handle_err(
                            ctx,
                            ValueError("Invalid term, campus, and career")
                        )
                        return
                case _:
                    await handle_err(ctx, ValueError("Invalid format"))
                    return
        case _:
            await handle_err(ctx, Exception("No subject provided"))
            return
    try:
        info = ps.get_subject(**params)
        pages = ColumnPages(
            title=f"{(subj := params['subject'].upper())} Courses Available at "
                  f"{campus.capitalize()} Campus",
            data=[(f"{subj} {num}", titlecase(crs.course_title))
                  for num, crs in info.courses.items()]
        )
        await ViewMenuPages(source=pages).start(ctx)
    except Exception as e:
        await handle_err(ctx, e)


@bot.command(description="Gets info about a specific course")
async def course(ctx, *args):
    def format_info(section_info: ps.SectionDetails) -> Embed:
        """Helper function for formatting embeds for section section_info."""
        embed = Embed(title=f"{section_info.subject_code} "
                            f"{section_info.course_num}: "
                            f"{titlecase(section_info.course_title)}",
                      description=section_info.desc, color=PITT_ROYAL)
        embed.add_field(name="Units", value=section_info.units)
        embed.add_field(name="Grading", value=section_info.grading)

        if len(section_info.components) > 0:
            embed.add_field(name="Components",
                            value="\n".join(section_info.components))
        if section_info.attrs:
            embed.add_field(name="Attributes",
                            value="\n".join(section_info.attrs))
        if section_info.prereqs:
            embed.add_field(name="Enrollment Reqs", value=section_info.prereqs)
        for _ in range((3 - (len(embed.fields) % 3)) % 3):
            # Empty fields serve as placeholders for alignment
            embed.add_field(name=ZERO_WIDTH_SPACE, value=ZERO_WIDTH_SPACE)
        return embed

    match [arg.lower() for arg in args]:
        # ?course [subject] [course num] ...
        case [subject, course_num, *others]:
            params = dict(subject=subject, course=course_num)
            # Set term and campus if specified
            match others:
                # ?course [subject] [course num] [term]
                case [arg] if arg in ps.TERMS:
                    params["term"] = ps.TERMS[arg]
                # ?course [subject] [course num] [campus]
                case [arg] if arg in ps.CAMPUSES:
                    params["campus"] = ps.CAMPUSES[arg]
                # ?course [subject] [course num] [term] [campus]
                case [arg1, arg2] if arg1 in ps.TERMS and arg2 in ps.CAMPUSES:
                    params["term"] = ps.TERMS[arg1]
                    params["campus"] = ps.CAMPUSES[arg2]
                # ?course [subject] [course num] [term] [campus]
                case [arg1, arg2] if arg2 in ps.TERMS and arg1 in ps.CAMPUSES:
                    params["term"] = ps.TERMS[arg2]
                    params["campus"] = ps.CAMPUSES[arg1]
                # ?course [subject] [course num] [term] [not a campus]
                case [arg, _] | [_, arg] if arg in ps.TERMS:
                    await handle_err(ctx, ValueError("Invalid campus"))
                # ?course [subject] [course num] [campus] [not a term]
                case [arg, _] | [_, arg] if arg in ps.CAMPUSES:
                    await handle_err(ctx, ValueError("Invalid term"))
                case []:  # ?course [subject] [course num]
                    pass
                case _:
                    await handle_err(ctx, ValueError("Incorrect format"))
            try:
                info = ps.get_course(**params)

                # Find first non-recitation section (not always first in list)
                sct = info.sections[0]
                for s in info.sections:
                    if s.section_type != "REC":
                        sct = s
                        break

                new_params = dict(class_num=sct.class_num)
                if "term" in params:
                    new_params["term"] = params["term"]
                new_info = ps.get_section(**new_params)
                await ctx.send(embed=format_info(new_info))
            except Exception as e:
                await handle_err(ctx, e)
        case [_]:
            await handle_err(ctx, Exception("No course number provided"))
        case _:
            await handle_err(ctx, Exception("No subject provided"))


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
            if sct.waitlist_size:
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
                    await handle_err(ctx, ValueError("Invalid campus"))
                # ?sections [subject] [course num] [campus] [not a term]
                case [arg, _] | [_, arg] if arg in ps.CAMPUSES:
                    await handle_err(ctx, ValueError("Invalid term"))
                case []:  # ?sections [subject] [course num]
                    pass
                case _:
                    await handle_err(ctx, ValueError("Incorrect format"))
            try:
                info = ps.get_course(**params)
                pages = EmbedPages(format_course(info))
                await ViewMenuPages(source=pages).start(ctx)
            except Exception as e:
                await handle_err(ctx, e)
        case [_]:
            await handle_err(ctx, Exception("No course number provided"))
        case _:
            await handle_err(ctx, Exception("No subject provided"))


@bot.command(description="Gets info about a specific course section")
async def section(ctx, *args):
    def format_section(sct: ps.SectionDetails) -> list[Embed]:
        """Helper function for formatting embeds for section sct."""
        embed1 = Embed(title=f"{sct.subject_code} {sct.course_num}: "
                             f"{titlecase(sct.course_title)} ({sct.class_num})",
                       color=PITT_ROYAL)
        embed1.add_field(name="Instructor", value=sct.instructor)
        embed1.add_field(name="Days/Times", value=sct.days_times)
        embed1.add_field(name="Dates", value=sct.dates)

        embed1.add_field(name="Location", value=sct.room)
        embed1.add_field(name="Campus", value=sct.campus)
        embed1.add_field(name="Status", value=sct.status)

        embed2 = Embed(title=f"{sct.subject_code} {sct.course_num}: "
                             f"{sct.course_title} ({sct.class_num})",
                       color=PITT_GOLD)
        embed2.add_field(name="Class Capacity", value=sct.total_capacity)
        embed2.add_field(name="Seats Taken", value=sct.seats_taken)
        embed2.add_field(name="Seats Open", value=sct.seats_open)
        if sct.seat_restrictions:
            embed2.add_field(
                name="Enrollment Restrictions",
                value="\n".join(f"{label} — {n}"
                                for label, n in sct.seat_restrictions.items())
            )
            embed2.add_field(name="Restricted Seats Open",
                             value=sct.restricted_seats)
            embed2.add_field(name="Unrestricted Seats Open",
                             value=sct.unrestricted_seats)
        embed2.add_field(name="Waitlist Capacity", value=sct.waitlist_capacity)
        embed2.add_field(name="Waitlist Size", value=sct.waitlist_size)
        # Empty fields serve as placeholders for alignment
        embed2.add_field(name=ZERO_WIDTH_SPACE, value=ZERO_WIDTH_SPACE)

        embeds = [embed1, embed2]
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
                    await handle_err(ctx, ValueError("Invalid term"))
                    return
                case []:  # ?section [class num]
                    pass
                case _:
                    await handle_err(ctx, ValueError("Incorrect format"))
                    return
            try:
                info = ps.get_section(**params)
                pages = EmbedPages(format_section(info))
                await ViewMenuPages(source=pages).start(ctx)
            except Exception as e:
                await handle_err(ctx, e)
        case _:
            await handle_err(ctx, Exception("No class number provided"))


@subjects.error
@courses.error
@course.error
@sections.error
@section.error
async def handle_err(ctx, e: Exception) -> None:
    await ctx.send(f"**{type(e).__name__}: {e}**")


bot.run(DISCORD_TOKEN)
