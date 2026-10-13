# Rules for system development

## Git

- Do not commit on your own.
- Do not do git push without explicit user permission.
- Do not change the Git history (rebase, reset --hard, force-push) without explicit permission.
- Do not delete branches, tags, or remote without confirmation.

## Code

- Follow the existing style and architecture of the project.
- Before adding a new abstraction, first check if there is already a suitable solution in the project.
- Do not duplicate existing logic.
- Prefer simple solutions to complex abstractions.
- Do not add dependencies unnecessarily.
- Do not use the deprecated API if there is a supported alternative.
- For public APIs/methods, maintain backward compatibility unless the project explicitly provides for breaking changes.
- Complex or non-obvious code must be accompanied by comments explaining why, not just what the code does.
- Do not leave TODO, FIXME and temporary workaround without explanation or issue/reference.
- Do not leave debug code, console.log, print, temporary files, or commented-out old code.
- All user-facing text in new components must go through i18n translation keys (namespace i18next). Hardcoding strings is prohibited. This ensures all features are immediately adapted for language switching without retroactive patching.
- All magic numbers and configuration constants (token expiry times, password lengths, iteration counts, pagination limits, field length constraints, etc.) must be extracted to a dedicated constants file (e.g., `constants.py`). Never store such values inline in business logic or schema definitions.

## Tests

- When adding a new function/method, it is mandatory to add tests.
- When fixing a bug, be sure to add a regression test that reproduces the bug.
- Run the existing test suite before completing the task.
- Do not delete or weaken tests just to make them pass.
- Do not change expected values in tests without understanding the reason for the change.
- Tests should test behavior, not a specific internal implementation.
- For critical business logic, aim for edge cases coverage.
- Do not use real external services in unit tests - use mocks/stubs/fakes.
- New integration tests should be explicitly separated from unit tests.

## Documentation

- Everything README.md write in Russian.
- The documentation should correspond to the current state of the code.
- Update the relevant documentation when changing the public API.
- The code examples in the documentation should be working and up-to-date.
- Breaking changes must be reflected in the documentation.
- Do not duplicate the same information in multiple places unnecessarily.
- Do not change specifications without user approval.

## Security

- Never keep secrets in the repository.  
- Do not output credentials, tokens, and sensitive data in logs.
- Do not disable TLS/SSL certificate validation without a very good reason.  
- Validate data coming from the user or external systems.  
- Do not execute shell commands with unverified user input.  
- Do not use eval and similar dangerous mechanisms unless absolutely necessary.  
- Before adding a dependency, check its origin and support.

## Other

- Do not modify code that is not relevant to the task at hand. If a separate problem is found, report it separately and do not fix it unnecessarily.
- Before changing the existing architecture, first examine the related files and dependencies.
- Before making changes, review the relevant OpenSpec specifications and ensure the implementation complies with them. Do not change OpenSpec specifications without explicit user approval.
- Before writing the code, find existing similar implementations.  
- If the requirements are ambiguous and the decision may significantly affect the architecture, ask a question first.  
- If the task is clear, do not ask unnecessary questions and immediately complete it.  
- After the changes, report:
    1. what has been changed
    2. what tests are running?
    3. test results
    4. what problems remain
- Do not claim that the tests/linters/build passed if they did not actually run.  
- Do not claim that the problem has been fixed if it has not been verified.
