# Testing Guidelines for DnD System

## General Rules

1. Use pytest for all test cases.
2. Each module should have its own test file (e.g., `test_modifiers.py` for `modifiers.py`).
3. Aim for complete coverage of all classes and methods, including subclasses and edge cases.
4. Use descriptive test names that explain what is being tested.
5. Use fixtures when appropriate to set up common test scenarios.
6. Clean up any global state modifications after each test.

## Understanding and Writing Tests

1. **Understand the Purpose**: Before modifying a test or the corresponding source code, ensure you fully understand the purpose of the test. Each test should verify a specific behavior or edge case.

2. **Read the Entire Test**: Don't focus solely on the failing assertion. Read the entire test to understand the setup, execution, and all assertions.

3. **Check Test Setup**: Ensure that the test is setting up the scenario correctly. Incorrect setup can lead to false negatives or positives.

4. **Verify Assertions**: Make sure the assertions are checking the correct conditions. Incorrect assertions can lead to tests passing when they shouldn't.

5. **Use Type Annotations**: Leverage type annotations in both tests and source code to catch type-related issues early.

6. **Test Inheritance Properly**: When testing inherited behavior, ensure that you're testing both the base class and its subclasses appropriately.

## Common Pitfalls and How to Avoid Them

1. **Changing Source Code Prematurely**: 
   - Pitfall: Modifying the source code to make a test pass without fully understanding the test's purpose.
   - Solution: Always start by understanding why the test is failing. Use debugging tools and print statements to investigate the actual behavior.

2. **Ignoring Type Checking Errors**: 
   - Pitfall: Using type ignore comments to bypass type checking errors in tests.
   - Solution: Address type issues properly. If a test intentionally uses incorrect types, document the reason clearly.

3. **Misunderstanding Inheritance in Tests**: 
   - Pitfall: Assuming that a test for a base class will automatically cover all subclasses.
   - Solution: Write specific tests for subclass behavior, especially when subclasses override or extend base class functionality.

4. **Overlooking Edge Cases**: 
   - Pitfall: Focusing only on the happy path and ignoring potential edge cases.
   - Solution: Explicitly test for edge cases, including invalid inputs, boundary conditions, and error scenarios.

5. **Neglecting Cleanup**: 
   - Pitfall: Failing to clean up global state after tests, leading to test interdependence.
   - Solution: Use pytest fixtures for setup and teardown. Ensure that any global state (like registries) is reset after each test.

6. **Race Conditions in Concurrent Tests**:
   - Pitfall: Relying on shared state or timing in concurrent tests, leading to inconsistent results.
   - Solution: Use thread-safe counters or synchronization primitives when testing concurrent behavior. Avoid relying on global state in concurrent tests.

7. **Incorrect Handling of None Values**:
   - Pitfall: Assuming that a value will never be None, especially in contextual or optional scenarios.
   - Solution: Always handle potential None values in callable functions, especially for context-aware modifiers.

8. **Mismatched UUIDs in Relational Tests**:
   - Pitfall: Not properly setting up or validating UUIDs when testing relationships between entities.
   - Solution: Ensure that source and target UUIDs are correctly set and validated in tests involving multiple entities.

## Best Practices

1. **Isolate Tests**: Each test should be independent of others. Avoid relying on the state from previous tests.

2. **Use Parameterized Tests**: For similar scenarios with different inputs, use pytest's parameterize feature to reduce code duplication.

3. **Mock External Dependencies**: Use mocking to isolate the unit under test from external dependencies.

4. **Regular Test Runs**: Run the full test suite regularly to catch regressions early.

5. **Test-Driven Development (TDD)**: Consider writing tests before implementing new features to ensure clear requirements and testable code.

6. **Document Test Cases**: Use docstrings or comments to explain complex test scenarios or the reasoning behind specific assertions.

7. **Review Test Coverage**: Regularly review test coverage to identify untested code paths.

8. **Maintain Test Code Quality**: Apply the same code quality standards to test code as you do to production code.

9. **Handle Asynchronous Operations**: When testing asynchronous code, ensure proper synchronization and avoid race conditions.

10. **Test Error Handling**: Include tests for error cases and ensure that appropriate exceptions are raised.

11. **Validate Complex Scenarios**: For classes like ModifiableValue, test interactions between different components (e.g., self_static, to_target_static, self_contextual, etc.).

12. **Check Computed Properties**: Ensure that computed properties (like score, advantage, critical, etc.) are correctly calculated based on all relevant modifiers.

Remember: The goal of testing is not just to increase code coverage, but to verify that the code behaves correctly under various scenarios. When a test fails, the first step should always be to understand why, rather than immediately changing the source code or the test itself.
