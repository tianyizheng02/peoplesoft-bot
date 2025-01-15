from os import getenv

from discord import Intents, Embed, Activity, ActivityType, Object
from discord.ext.commands import Bot, Context
from dotenv import load_dotenv

import course
from course import Course, CourseDetails, Section
from embed_pages import EmbedPages
import utils
from utils import ZERO_WIDTH, PITT_ROYAL, PITT_GOLD

load_dotenv()
DISCORD_TOKEN = getenv("DISCORD_TOKEN")

MY_ID = getenv("MY_ID")
if MY_ID is None:
    raise IOError("Couldn't find personal Discord ID in .env")

TEST_SERVER_ID = getenv("TEST_SERVER_ID")
if TEST_SERVER_ID is not None:
    TEST_SERVER = Object(id=TEST_SERVER_ID)
else:
    raise IOError("Couldn't find test server ID in .env")

CURRENT_TERM = "2254"


class PeopleSoftBot(Bot):
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        intents = Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=self.prefix, intents=intents)

    async def setup_hook(self) -> None:
        self.tree.copy_global_to(guild=TEST_SERVER)
        await self.tree.sync(guild=TEST_SERVER)


bot = PeopleSoftBot(prefix="??")


@bot.event
async def on_ready() -> None:
    await bot.change_presence(
        activity=Activity(type=ActivityType.watching, name=f"for {bot.prefix}help")
    )
    print(f"Running on {(num := len(bot.guilds))} server{'s' if num > 1 else ''}:")
    for guild in bot.guilds:
        print(f"\t{guild.name:<20}\t{guild.id}")


@bot.command(description="pong", hidden=True)
async def ping(ctx: Context) -> None:
    """Ping-pong command to test connection (developer only)"""
    assert MY_ID is not None
    if ctx.author.id == int(MY_ID):
        await ctx.send("pong")


@bot.hybrid_command(hidden=True)
async def sync(ctx: Context) -> None:
    """Sync command tree (developer only)"""
    assert MY_ID is not None
    if ctx.author.id == int(MY_ID):
        await ctx.defer()  # To avoid timing out for slash commands
        synced = await bot.tree.sync()
        await ctx.send("Command tree synced")
        await ctx.send(" ".join(com.name for com in synced if com))
    else:
        await ctx.send("This is a developer-only command")


@bot.hybrid_command(name="subjects")
async def get_subjects(ctx: Context) -> None:
    """Get available subjects"""
    try:
        await ctx.defer()  # To avoid timing out for slash commands
        info = course._get_subjects()["subjects"]
        page_data = utils.to_column_embeds(
            entries=[(subj["subject"], subj["descr"]) for subj in info],
            title="Available Subjects",
        )
        await EmbedPages(page_data).start(ctx=ctx)
    except Exception as e:
        await handle_err(ctx, e)  # type: ignore


@bot.hybrid_command(name="courses")  # type: ignore
async def get_courses(ctx: Context, subject: str) -> None:
    """Get available courses for a given subject"""
    try:
        await ctx.defer()  # To avoid timing out for slash commands
        info = course.get_subject_courses(subject.upper())
        page_data = utils.to_column_embeds(
            entries=[
                (f"{subject.upper()} {num}", utils.titlecase(crs.course_title))
                for num, crs in info.courses.items()
            ],
            title=f"Available {subject.upper()} Courses",
        )
        await EmbedPages(page_data).start(ctx)
    except Exception as e:
        await handle_err(ctx, e)  # type: ignore


@bot.hybrid_command(name="course")  # type: ignore
async def get_course(ctx: Context, subject: str, course_num: str, term: str = CURRENT_TERM) -> None:
    """Get info about a given course"""

    def format_course_details(info: CourseDetails) -> Embed:
        embed = Embed(
            title=f"{info.course.subject_code} {info.course.course_number}: "
            f"{utils.titlecase(info.course.course_title)}",
            description=info.course_description,
            color=PITT_ROYAL,
        )
        if info.credit_range:
            min_creds, max_creds = info.credit_range
            embed.add_field(
                name="Units",
                value=f"{min_creds}–{max_creds}" if min_creds != max_creds else min_creds,
            )
        else:
            embed.add_field(name=ZERO_WIDTH, value=ZERO_WIDTH)  # Empty field for alignment

        if info.components:
            embed.add_field(
                name="Components",
                value="\n".join(component.component for component in info.components),
            )
        if info.attributes:
            embed.add_field(
                name="Attributes",
                value="\n".join(attr.attribute for attr in info.attributes),
            )
        if info.requisites:
            embed.add_field(name="Enrollment Reqs", value=info.requisites)
        for _ in range((3 - (len(embed.fields) % 3)) % 3):
            embed.add_field(name=ZERO_WIDTH, value=ZERO_WIDTH)  # Empty field for alignment
        return embed

    try:
        await ctx.defer()  # To avoid timing out for slash commands
        info = course.get_course_details(term, subject.upper(), course_num)
        await ctx.send(embed=format_course_details(info))
    except Exception as e:
        await handle_err(ctx, e)  # type: ignore


@bot.hybrid_command(name="sections")  # type: ignore
async def get_sections(
    ctx: Context, subject: str, course_num: str, term: str = CURRENT_TERM
) -> None:
    """Get available sections for a given course"""

    def format_course_sections(course_info: CourseDetails) -> list[Embed]:
        if not course_info.sections:
            raise AttributeError(
                f"No sections found for "
                f"{course_info.course.subject_code} {course_info.course.course_number}"
            )

        embeds: list[Embed] = []
        for i, sct in enumerate(course_info.sections, start=1):
            if not sct.meetings:
                raise AttributeError(
                    f"No meeting times found for "
                    f"{course_info.course.subject_code} {course_info.course.course_number} "
                    f"({sct.section_number})"
                )
            if len(sct.meetings) > 1:
                raise NotImplementedError(
                    f"{course_info.course.subject_code} {course_info.course.course_number} "
                    f"({sct.section_number}) "
                    f"has multiple meeting slots, which is not currently supported"
                )
            meeting = sct.meetings[0]

            embed = Embed(
                title=f"{course_info.course.subject_code} {course_info.course.course_number}: "
                f"{utils.titlecase(course_info.course.course_title)}",
                color=PITT_ROYAL if i % 2 else PITT_GOLD,
            )
            embed.add_field(name="Type", value=sct.section_type)
            embed.add_field(name="Section #", value=sct.section_number)
            embed.add_field(name="Class #", value=sct.class_number)
            embed.add_field(
                name="Instructor(s)",
                value=(
                    ", ".join(instructor.name for instructor in sct.instructors)
                    if sct.instructors
                    else ZERO_WIDTH
                ),
            )
            # TODO: location not available from course API
            # embed.add_field(name="Location", value=meeting.location)
            embed.add_field(
                name="Days/Times",
                value=f"{meeting.days} "
                f"{utils.reformat_time_str(meeting.start_time)}–"
                f"{utils.reformat_time_str(meeting.end_time)}",
            )
            embed.add_field(
                name="Dates",
                value=f"{meeting.start_date[:-5]}–{meeting.end_date[:-5]}",
            )
            embed.add_field(name="Status", value=sct.status)
            if sct.details:
                embed.add_field(
                    name="Waitlist Size",
                    value=f"{sct.details.wait_list_total}/{sct.details.wait_list_capacity}",
                )
                embed.add_field(name=ZERO_WIDTH, value=ZERO_WIDTH)  # Empty field for alignment
            embed.set_footer(text=f"Page {i} of {len(course_info.sections)}")
            embeds.append(embed)
        return embeds

    try:
        await ctx.defer()  # To avoid timing out for slash commands
        info = course.get_course_details(term, subject.upper(), course_num)
        page_data = format_course_sections(info)
        await EmbedPages(page_data).start(ctx)
    except Exception as e:
        await handle_err(ctx, e)  # type: ignore


@bot.command(name="section")
async def get_section(ctx: Context, class_num: str, term: str = CURRENT_TERM) -> None:
    """Get info about a given section"""

    def format_section(crse: Course, sct: Section) -> Embed:
        """Helper function for formatting embeds for section sct."""
        if not sct.meetings:
            raise AttributeError(
                f"No meeting times found for "
                f"{course_info.subject_code} {course_info.course_number} "
                f"({sct.section_number})"
            )
        if len(sct.meetings) > 1:
            raise NotImplementedError(
                f"{course_info.subject_code} {course_info.course_number} "
                f"({sct.section_number}) "
                f"has multiple meeting slots, which is not currently supported"
            )
        meeting = sct.meetings[0]

        embed = Embed(
            title=f"{crse.subject_code} {crse.course_number}: {utils.titlecase(crse.course_title)} "
            f"({sct.class_number})",
            color=PITT_ROYAL,
        )
        if sct.instructors:
            embed.add_field(
                name="Instructor(s)",
                value=", ".join(instructor.name for instructor in sct.instructors),
            )
        elif meeting.instructors:
            embed.add_field(
                name="Instructor(s)",
                value=", ".join(instructor.name for instructor in meeting.instructors),
            )
        else:
            embed.add_field(name=ZERO_WIDTH, value=ZERO_WIDTH)  # Empty field for alignment
        embed.add_field(
            name="Days/Times",
            value=f"{meeting.days} {meeting.start_time}–{meeting.end_time}",
        )
        embed.add_field(
            name="Dates",
            value=f"{meeting.start_date[:-5]}–{meeting.end_date[:-5]}",
        )
        # TODO: location not available from course API
        # embed1.add_field(name="Location", value=sct.room)
        # TODO: campus not available from course API
        # embed1.add_field(name="Campus", value=sct.campus)
        embed.add_field(name="Status", value=sct.status)
        embed.add_field(name=ZERO_WIDTH, value=ZERO_WIDTH)  # Empty field for alignment
        embed.add_field(name=ZERO_WIDTH, value=ZERO_WIDTH)  # Empty field for alignment
        if sct.details:
            embed.add_field(name="Class Capacity", value=sct.details.class_capacity)
            embed.add_field(name="Seats Taken", value=sct.details.enrollment_total)
            embed.add_field(name="Seats Open", value=sct.details.enrollment_available)
            if int(sct.details.enrollment_available) == 0:
                embed.add_field(name="Waitlist Capacity", value=sct.details.wait_list_capacity)
                embed.add_field(name="Waitlist Size", value=sct.details.wait_list_total)
                embed.add_field(name=ZERO_WIDTH, value=ZERO_WIDTH)  # Empty field for alignment
        return embed

    try:
        await ctx.defer()  # To avoid timing out for slash commands
        course_info, section_info = course.get_section_details(term, class_num)
        await ctx.send(embed=format_section(course_info, section_info))
    except Exception as e:
        await handle_err(ctx, e)  # type: ignore


@get_subjects.error
@get_courses.error
@get_course.error
@get_sections.error
@get_section.error
async def handle_err(ctx: Context, e: Exception) -> None:  # type: ignore
    await ctx.send(f"**{type(e).__name__}: {e}**")


if __name__ == "__main__":
    if DISCORD_TOKEN is not None:
        bot.run(DISCORD_TOKEN)
