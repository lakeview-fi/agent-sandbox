You are working in a Docker Sandbox on a copy of a project under git.

<!-- ADAPT: replace the steps below with the acceptance task the user confirmed. Name the exact
change, the commands to run and what to report. Keep the last step: it makes the result checkable.
With a read-only mount, add a first step that copies the project to a writable directory. -->

1. Add a regression test for <named behaviour> to <test file>. Follow the existing tests in that file (same style, same helpers). Do not change code outside the tests.
2. Run the test file, then the project's lint check.
3. Install one Linux package with the system package manager, and one language package the project needs.
4. Fetch the documentation page of one library the change depends on with `curl -sS <url> -o /dev/null -w "%{http_code}"` and report the HTTP status code.
5. Reply with: the test you added (its name), the exact pass/fail line from each command in step 2, the result of step 3, and the HTTP status from step 4. Do not claim a result you did not see.
