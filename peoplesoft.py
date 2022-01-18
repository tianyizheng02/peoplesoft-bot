"""
The Pitt API, to access workable data of the University of Pittsburgh
Copyright (C) 2015 Ritwik Gupta

Modified 2022 Tianyi Zheng

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License along
with this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""
from collections.abc import Generator
from json import loads
import re
from typing import NamedTuple

import parse
from requests import get
from requests_html import HTMLSession

PSMOBILE_URL = "https://psmobile.pitt.edu/app/catalog/"
CLASS_SEARCH_URL = PSMOBILE_URL + "classSearch"
CLASS_SEARCH_API_URL = PSMOBILE_URL + "getClassSearch"
SCT_DETAIL_URL = PSMOBILE_URL + "classsection/UPITT/{term}/{class_num}"

TERMS = {
    "fall": "2221",
    "spring": "2224",
    "summer": "2227"
}
CURR_TERM = TERMS["spring"]
CAMPUSES = {
    "main": "PIT",
    "bradford": "UPB",
    "greensburg": "UPG",
    "johnstown": "UPJ",
    "titusville": "UPT"
}
MAIN_CAMPUS = CAMPUSES["main"]
CAREERS = {
    "undergrad": "UGRD",
    "dental": "DMED",
    "grad": "GRAD",
    "law": "LAW",
    "med": "MEDS"
}
UNDERGRAD = CAREERS["undergrad"]

LABEL_MAP = {
    "Session": "session",
    "Class Number": "class_num",
    "Career": "career",
    "Dates": "dates",
    "Units": "units",
    "Grading": "grading",
    "Description": "desc",
    "Add Consent": "consent",
    "Class Notes": "notes",
    "Enrollment Requirements": "prereqs",
    "Class Attributes": "attrs",
    "Instructor(s)": "instructor",
    "Meets": "days_times",
    "Room": "room",
    "Campus": "campus",
    "Location": "campus",
    "Components": "components",
    "Status": "status",
    "Seats Taken": "seats_taken",
    "Seats Open": "seats_open",
    "Combined Section Capacity": "total_capacity",
    "Class Capacity": "total_capacity",
    "Unrestricted Seats": "unrestricted_seats",
    "Restricted Seats": "restricted_seats",
    "Wait List Total": "waitlist_size",
    "Wait List Capacity": "waitlist_capacity"
}

COMBINED_SCT_PATTERN = parse.compile(
    "{course_name}\n"
    "{subject_code} {course_num} - {section_num} ({class_num})\n"
    "Status: {status}\n"
    "Seats Taken: {seats_taken:d}\n"
    "Wait List Total: {waitlist_size:d}")
CREDIT_UNITS_PATTERN = parse.compile("{:d} units")
SCT_PATTERN = parse.compile(
    "Section: {section_num}-{section_type} ({class_num})\n"
    "Session: {session}\n"
    "Days/Times: {days_times}\n"
    "Room: {room}\n"
    "Instructor: {instructor}\n"
    "Meeting Dates: {dates}\n"
    "Status: {status}\n")

SCT_TITLE_PATTERN = parse.compile("{subject_code} {course_num} - {section_num}")
SCT_WAITLIST_PATTERN = parse.compile(
    "Section: {section_num}-{section_type} ({class_num})\n"
    "Session: {session}\n"
    "Days/Times: {days_times}\n"
    "Room: {room}\n"
    "Instructor: {instructor}\n"
    "Meeting Dates: {dates}\n"
    "Status: {status}\n"
    "Wait List Total: {waitlist_size}")
COURSE_INFO_PATTERN = parse.compile("{subject_code} {course_num} - "
                                    "{course_title}")

SCT_DETAIL_INT_FIELD = {
    "seats_taken",
    "seats_open",
    "total_capacity",
    "unrestricted_seats",
    "restricted_seats",
    "waitlist_size",
    "waitlist_capacity"
}


class CombinedSection(NamedTuple):
    term: str
    course_name: str
    subject_code: str
    course_num: str
    section_num: str
    class_num: str
    status: str
    seats_taken: int
    waitlist_size: int


class SectionDetails(NamedTuple):
    subject_code: str
    course_num: str
    course_title: str
    section_num: str
    term: str

    session: str
    class_num: str
    career: str
    units: int
    grading: str

    instructor: str
    days_times: str
    dates: str
    room: str
    campus: str
    components: list[str]

    status: str
    seats_taken: int
    seats_open: int
    total_capacity: int
    unrestricted_seats: int
    restricted_seats: int
    waitlist_size: int
    waitlist_capacity: int

    desc: str = ""
    prereqs: str | None = None
    consent: str | None = None
    notes: str | None = None
    attrs: list[str] | None = None
    seat_restrictions: dict[str, int] | None = None
    combined_sections: list[CombinedSection] | None = None


class SubjectCode(NamedTuple):
    subject_code: str
    desc: str
    academic_group: str


class Section(NamedTuple):
    term: str
    session: str
    section_num: str
    section_type: str
    class_num: str
    days_times: str
    room: str
    instructor: str
    dates: str
    status: str
    waitlist_size: str | None


class Course(NamedTuple):
    subject_code: str
    course_num: str
    course_title: str
    sections: list[Section] | None = None


class Subject(NamedTuple):
    subject_code: str
    courses: dict[str, Course]
    term: str | None = None


def _get_subject_json(campus: str) -> Generator[dict, None, None]:
    """Parse PSMobile JSON into an iterator of subject codes."""
    text = get(CLASS_SEARCH_URL).text
    s = re.search(r"(?=subjects\s*:\s).*,", text)
    text = s.group()[:-1]
    text = text[text.find(":") + 1:]
    data = loads(text)

    # Filter out subject codes that are exclusively for other campuses
    for code in data:
        if any(v["campus"] == campus for v in code["campuses"].values()):
            yield code


def _parse_class_search(resp, term: str) -> dict[str, Course]:
    """Parse the HTMLResponse resulting from a PSMobile query with a given
    payload."""
    if resp.html.search("No classes found matching your criteria"):
        raise ValueError("Criteria didn't find any classes")
    if resp.html.search("The search took too long to respond, "
                        "please try selecting additional search criteria."):
        raise TimeoutError("Search response took too long")
    if resp.status_code != 200:
        raise ConnectionError("PeopleSoft is unavailable")

    courses: dict[str, Course] = {}
    elements = resp.html.find("div")

    course = None
    for element in elements:
        if "section-body" not in element.attrs["class"]:
            print(element.text, end="\n\n")
            if "secondary-head" in element.attrs["class"]:
                content = COURSE_INFO_PATTERN.parse(element.text)
                course = Course(**content.named, sections=[])
                courses[content["course_num"]] = course
            elif "section-content" in element.attrs["class"]:
                content = SCT_WAITLIST_PATTERN.parse(element.text)
                if content is None:
                    content = SCT_PATTERN.parse(element.text + "\n")
                    section = Section(
                        **content.named, term=term, waitlist_size=None)
                else:
                    section = Section(**content.named, term=term)
                course.sections.append(section)
    return courses


def _validate_campus(campus: str) -> str:
    """Check if the campus is a valid campus."""
    campus = campus.upper()
    if campus not in CAMPUSES.values():
        raise ValueError("Invalid campus")
    return campus


def _validate_career(career: str) -> str:
    """Check whether the career is a valid career."""
    career = career.upper()
    if career not in CAREERS.values():
        raise ValueError("Invalid career")
    return career


def _validate_term(term: str) -> None:
    """Check if the term is currently being supported by PeopleSoft."""
    if term not in TERMS.values():
        raise ValueError("Invalid Pitt term")


def _validate_subject(subject: str) -> str:
    """Check if the subject code consists of only letters."""
    if not subject.isalpha():
        raise ValueError("Invalid subject")
    return subject.upper()


def _validate_course(course: str) -> str:
    """Check if the course number entered is a 4-digit number and extend it to 4
    digits long if possible."""
    if not course.isdigit():
        raise ValueError("Invalid course number")
    course_length = len(course)
    if course_length < 4:
        return ("0" * (4 - course_length)) + course
    elif course_length > 4:
        raise ValueError("Invalid course number")
    return course


def _validate_section(section: str):
    """Check if section number is a 5-digit number."""
    if not section.isdigit() or len(section) != 5:
        raise ValueError("Invalid section number")


def _get_payload(term: str = CURR_TERM, campus: str = MAIN_CAMPUS,
                 career: str = "", subject: str = "", course: str = "",
                 section: str = "") -> tuple[HTMLSession, dict[str, str]]:
    """Make payload for request and generate CSRFToken for the request."""

    session = HTMLSession()  # Generate new CSRFToken
    session.get(CLASS_SEARCH_URL)
    payload = {
        "CSRFToken": session.cookies["CSRFCookie"],
        "term": term,
        "campus": campus,
        "acad_career": career,
        "subject": subject,
        "catalog_nbr": course,
        "class_nbr": section
    }
    return session, payload


def get_subject_codes(campus: str = MAIN_CAMPUS) -> list[str]:
    """Get list of available subject codes for a Pitt campus. The campus is
    main campus by default."""
    return [code["subject"] for code in _get_subject_json(campus)]


def get_detailed_subject_codes(campus: str = MAIN_CAMPUS) -> list[SubjectCode]:
    """Get list of available subjects codes for a Pitt campus as well as the
    subjects' full names. The campus is main campus by default."""
    return [SubjectCode(
        subject_code=code["subject"], desc=code["descr"],
        academic_group=code["acad_groups"]["group0"]["acad_group"])
        for code in _get_subject_json(campus)]


def get_subject(subject: str, term: str = CURR_TERM,
                campus: str = MAIN_CAMPUS, career: str = "") -> Subject:
    """Get a list of courses available for a subject. The term is the current
    term, the campus is main campus, and the career is unspecified by
    default."""
    subject = _validate_subject(subject)
    _validate_term(term)
    campus = _validate_campus(campus)
    if career != "":
        career = _validate_career(career)
    session, payload = _get_payload(
        term=term, campus=campus, career=career, subject=subject)
    response = session.post(url=CLASS_SEARCH_API_URL, data=payload)
    courses = _parse_class_search(resp=response, term=term)
    subject = Subject(subject_code=subject, term=term, courses=courses)
    return subject


def get_course(subject: str, course: str, term: str = CURR_TERM,
               campus: str = MAIN_CAMPUS) -> Course | None:
    """Get details on all sections of a course given the subject and course
    number. The term is the current term and the campus is main campus by
    default."""
    subject = _validate_subject(subject)
    course = _validate_course(course)
    _validate_term(term)
    campus = _validate_campus(campus)
    try:
        session, payload = _get_payload(
            term=term, campus=campus, subject=subject, course=course)
        response = session.post(url=CLASS_SEARCH_API_URL, data=payload)
        course, *_ = _parse_class_search(response, term).values()
    except ValueError:
        raise ValueError("Course doesn't exist")
    return course


def get_section(class_num: str, term: str = CURR_TERM) -> SectionDetails:
    """Get details on a specific section of a course given a class number. The
    term is the current term by default."""
    data = dict(term=term, class_num=class_num)
    session = HTMLSession()
    url = SCT_DETAIL_URL.format(term=term, class_num=class_num)
    resp = session.get(url)

    try:
        # The course title is in the HTML head rather than the body
        title = SCT_TITLE_PATTERN.parse(
            resp.html.xpath("/html/head/title")[0].text)
        data.update(**title.named)

        elements = resp.html.xpath("/html/body/section/section/div")
        # Available room info is presented as a link rather than plaintext
        try:
            room = resp.html.xpath("/html/body/section/section/a/div")[0]
            elements.insert(15, room)
        except IndexError:
            print("No room info available")
        heading = ""
        for element in elements:
            print(element.text, end="\n\n")
            if "role" in element.attrs:
                heading = element.text

                # Heading is course title (which is always in all caps)
                if heading.isupper():
                    data["course_title"] = heading
                continue

            if heading == "Combined Section":
                if "combined_sections" not in data:
                    data["combined_sections"] = []
                content = COMBINED_SCT_PATTERN.parse(element.text)
                combined_section = CombinedSection(**content.named, term=term)
                data["combined_sections"].append(combined_section)
                continue

            if "\n" not in element.text:
                continue

            label, content, *extra = element.text.split("\n")

            if heading == "Enrollment Restrictions":
                if "seat_restrictions" not in data:
                    data["seat_restrictions"] = {}
                data["seat_restrictions"][label] = int(
                    re.search(r"\d+", content).group())
                continue

            if label in LABEL_MAP:
                label = LABEL_MAP[label]
                if label == "components":
                    content = content.split(", ")
                elif label == "units":
                    content = CREDIT_UNITS_PATTERN.parse(content)[0]
                elif label == "attrs":
                    content = [content] + extra
                elif label in SCT_DETAIL_INT_FIELD:
                    content = int(content)

                data[label] = content
    except AttributeError:
        raise ValueError("Section doesn't exist")
    return SectionDetails(**data)


if __name__ == "__main__":
    print(get_detailed_subject_codes())
