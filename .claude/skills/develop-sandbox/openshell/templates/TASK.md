You are working in /sandbox/src, a project under git. It has one baseline commit.

<!-- ADAPT: replace the steps below with the acceptance task the user confirmed. Name the exact
change, the commands to run and what to report. Keep the last step: it makes the result checkable. -->

1. Add a regression test for <named behaviour> to <test file>. Follow the existing tests in that file (same style, same helpers). Do not change code outside the tests.
2. Run the test file, then the project's lint check. Use the commands in sandbox/run.sh, `project_checks`.
3. Fetch the documentation page of one library the change depends on with `curl -sS <url> -o /dev/null -w "%{http_code}"` and report the HTTP status code.
4. Reply with: the test you added (its name), the exact pass/fail line from each command in step 2, and the HTTP status from step 3. Do not claim a result you did not see.
