# PeopleSoft Bot

PeopleSoft Bot is a Discord bot that retrieves data from PeopleSoft, the student information system used by the University of Pittsburgh.
I created it as a way for Pitt students on Discord to easily search for info on classes without needing to take the time to do it themselves.

## Usage

The bot currently supports the following commands:

- `??subjects`: Get subjects with their abbreviated subject codes

- `??courses <subject_code>`: Gets courses for a specific subject

- `??course <subject_code> <course_number> [term]`: Get info about a specific course

- `??sections <subject_code> <course_number> [term]`: Get sections for a specific course

- `??section <class_number> [term]`: Get info about a specific section of a course

Where applicable, the default term is the current term (Spring 2025).

## Credits

The bot uses modified code from [PittAPI](https://github.com/pittcsc/PittAPI) by [Ritwik Gupta](https://github.com/RitwikGupta) and the [CSC @ Pitt](https://github.com/pittcsc).
