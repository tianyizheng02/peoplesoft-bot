# PeopleSoft Bot

**UPDATE: This bot no longer works, as Pitt has since shut down PSMobile.**

PeopleSoft Bot is a Discord bot that retrieves data from PeopleSoft, the student information system used by the University of Pittsburgh.
I created it as a way for Pitt students on Discord to easily search for info on classes without needing to take the time to do it themselves.

The bot was written in Python and deployed using Heroku.
It works by scraping data from PSMobile, the mobile site for PeopleSoft that's accessible without a Pitt login.

## Usage

The bot currently supports the following commands:

- `??subjects [campus]`: Gets list of subjects with their abbreviated subject codes

- `??courses <subject_code> [campus] [term]`: Gets list of courses for a specific subject

- `??course <subject_code> <course_number> [campus] [term]`: Gets info about a specific course

- `??sections <subject_code> <course_number> [campus] [term]`: Gets list of sections for a specific course

- `??section <class_number> [term]`: Gets info about a specific section of a course

Where applicable, the default campus and term are main campus and the current term, respectively.

## Credits

The bot uses modified code from [PittAPI](https://github.com/pittcsc/PittAPI) by [Ritwik Gupta](https://github.com/RitwikGupta).
