# Repository Licensing Map

[← Back to Project README](README.md)

**Streaming System + Compass** uses separate licenses according to content role:

```text
software and executable repository content → Apache License 2.0
documentation and prose                  → CC BY 4.0
```

## Software and Executable Content

The [Apache License, Version 2.0](LICENSE) applies to implementation-oriented and executable repository content, including:

* source and implementation content under `src/**`
* test code and executable fixtures under `tests/**`
* `db/**`, including migrations
* executable experiment code under `experiments/**`
* executable or substantial standalone example implementations
* configuration used to execute, validate, or test the software, including `.github/workflows/**`, `.env.example`, `docker-compose.yml`, `pytest.ini`, and `requirements.txt`
* equivalent implementation code or executable scripts wherever they appear in the repository

## Documentation and Prose

Unless otherwise noted, prose documentation and research material are licensed under the [Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/) (CC BY 4.0). This includes:

* `README.md`
* `docs/**`
* the prose in `NOTICE.md` and this licensing map
* other repository Markdown whose primary role is documentation, guidance, explanation, or architecture history
* non-executable recorded experiment evidence and research reports, including benchmark evidence artifacts under `experiments/**/evidence/**`

CC BY 4.0 permits sharing and adaptation, including commercial use, with appropriate attribution and an indication of changes where applicable.

A suggested documentation attribution is:

```text
Streaming System + Compass documentation by Yen-Hua Chen.
Licensed under CC BY 4.0.
Original source: https://github.com/hikaru-212/streaming-system-compass
```

The suggested wording is not required verbatim and does not add a condition to the Apache License 2.0 software grant.

## Markdown Code Examples

Ordinary illustrative code snippets remain part of the CC BY 4.0 document that contains them. This repository does not attempt line-by-line dual licensing of those snippets.

Substantial standalone executable or example software is Apache-2.0 content even when Markdown is used to explain or present it. The content's primary role, rather than its filename extension alone, determines the boundary.

## License References

* [Apache License 2.0](LICENSE)
* [Project Notice](NOTICE.md)
* [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
