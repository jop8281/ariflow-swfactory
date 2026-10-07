# Node JUnit fixtures

These reports were generated with Node v22.23.3 using:

```sh
node --test --test-reporter=junit node22-standalone.test.mjs
node --test --test-reporter=junit node22-suite.test.mjs
node --test --test-reporter=junit node22-nested.test.mjs
```

Each command exits zero even though its TODO case emits both `skipped` and
`failure`. The parser must retain the failure and count each case once. Nested
Node suites summarize their immediate children, while other JUnit reporters
summarize descendant cases. The parser checks declared summaries against these
two forms, then returns case totals without adding suite totals again.

Times, hostnames, and absolute source paths are normalized. All test counts,
outcomes, and nesting match the original reports. These fixtures exercise report
parsing without requiring Node during the Python suite. Existing skip policy
remains in `TestResult.ok`.
