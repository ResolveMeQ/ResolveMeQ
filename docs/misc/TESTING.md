# ResolveMe Testing Guide

## 🧪 Testing Overview

This project includes comprehensive tests to ensure the autonomous agent system works correctly before deployments.

## 📁 Test Files

- `test_autonomous_agent.py` - Main test suite for autonomous agent functionality
- `run_tests_simple.sh` - Simple test runner focused on autonomous agent tests
- `run_tests.sh` - Complete test runner with linting and full app tests
- `test_settings.py` - Test-specific Django settings (uses in-memory SQLite)
- `.github/workflows/tests.yml` - CI/CD pipeline for automated testing

## ⚙️ Test Configuration

The project uses Django's built-in test runner with custom test settings:

- **Test Database**: In-memory SQLite for speed
- **Celery**: Configured for synchronous execution during tests  
- **Agent Processing**: Mock agent responses to avoid external dependencies
- **Signals**: Modified to prevent network calls during testing

## 🚀 Running Tests

### Quick Test Run
```bash
# Run all autonomous agent tests (recommended)
./run_tests_simple.sh

# Run all tests including app tests
./run_tests.sh

# Run only autonomous agent tests
python manage.py test test_autonomous_agent --settings=test_settings -v 2

# Run Django app tests
python manage.py test --settings=test_settings
```

### Detailed Test Commands
```bash
# Run with specific test settings
python manage.py test test_autonomous_agent --settings=test_settings -v 2

# Run specific test class
python manage.py test test_autonomous_agent.AutonomousAgentTest --settings=test_settings -v 2

# Run specific test method
python manage.py test test_autonomous_agent.AutonomousAgentTest.test_high_confidence_auto_resolve --settings=test_settings -v 2
```

## 🔍 Test Coverage

### Core Components Tested

✅ **User Model**
- User creation and validation
- Custom fields and methods
- Authentication functionality

✅ **Ticket Model**
- Ticket creation and lifecycle
- Status transitions
- Interaction tracking

✅ **Autonomous Agent**
- Decision-making logic
- Confidence-based actions
- Auto-resolve, escalate, clarify workflows

✅ **Knowledge Base API**
- Article retrieval endpoints
- Search functionality
- Agent access permissions

✅ **Slack Integration**
- User ID extraction
- Message formatting
- Interactive responses

✅ **Solution Management**
- Solution creation and tracking
- Success rate monitoring

### Test Categories

1. **Unit Tests** - Individual component functionality
2. **Integration Tests** - Component interaction testing
3. **End-to-End Tests** - Complete workflow testing
4. **Performance Tests** - Load and efficiency testing
5. **API Tests** - External interface testing

## 📊 Test Metrics

The test suite measures:
- Code coverage percentage
- Test execution time
- Pass/fail rates
- Performance benchmarks

## 🔧 Setting Up Tests

### Prerequisites
```bash
# Install test dependencies
pip install pytest pytest-django pytest-cov coverage

# Set environment variables
export DJANGO_SETTINGS_MODULE=resolvemeq.settings
```

### Database Setup
Tests use an in-memory SQLite database for speed:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
```

## 🎯 Test Scenarios

### Autonomous Agent Scenarios

1. **High Confidence Auto-Resolve**
   - Input: Simple password reset request
   - Expected: Immediate auto-resolution
   - Verification: Ticket status = "resolved"

2. **Medium Confidence Follow-up**
   - Input: Network connectivity issue
   - Expected: Solution provided + follow-up scheduled
   - Verification: Follow-up task created

3. **Low Confidence Escalation**
   - Input: Complex security incident
   - Expected: Immediate escalation to security team
   - Verification: Ticket assigned to security team

4. **Clarification Request**
   - Input: Vague issue description
   - Expected: Clarification questions sent to user
   - Verification: Status = "pending_clarification"

### API Testing Scenarios

1. **Knowledge Base Access**
   - Test article retrieval
   - Test search functionality
   - Test filtering and pagination

2. **Slack Integration**
   - Test user ID extraction
   - Test message delivery
   - Test interactive button responses

## 🐛 Debugging Tests

### Common Issues

1. **Import Errors**
   ```bash
   # Check Django setup
   python -c "import django; django.setup()"
   ```

2. **Database Issues**
   ```bash
   # Reset test database
   python manage.py migrate --run-syncdb
   ```

3. **Mock Failures**
   ```bash
   # Check mock configurations
   python -m pytest test_autonomous_agent.py::TicketProcessingTest -v -s
   ```

### Test Debugging Commands
```bash
# Run with verbose output
python -m pytest test_autonomous_agent.py -v -s --tb=long

# Run specific failing test
python -m pytest test_autonomous_agent.py::TestClass::test_method -v

# Run with pdb debugger
python -m pytest test_autonomous_agent.py --pdb
```

## 📈 Continuous Integration

### GitHub Actions Pipeline

The CI/CD pipeline automatically:
1. Sets up test environment
2. Installs dependencies
3. Runs comprehensive test suite
4. Generates coverage reports
5. Checks for security issues
6. Uploads results to Codecov

### Pre-commit Hooks

Add to `.git/hooks/pre-commit`:
```bash
#!/bin/bash
./run_tests.sh
if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi
```

## 🔄 Test Maintenance

### Adding New Tests

1. **For new models:**
   ```python
   class NewModelTest(TestCase):
       def test_model_creation(self):
           # Test logic here
   ```

2. **For new API endpoints:**
   ```python
   class NewAPITest(APITestCase):
       def test_endpoint_response(self):
           # Test logic here
   ```

3. **For new autonomous actions:**
   ```python
   def test_new_autonomous_action(self):
       # Test agent decision logic
   ```

### Updating Existing Tests

- Maintain test isolation
- Update mocks when APIs change
- Keep test data realistic
- Document complex test scenarios

## 📋 Test Checklist

Before each commit, verify:
- [ ] All tests pass locally
- [ ] No linting errors
- [ ] Test coverage maintained
- [ ] New features have tests
- [ ] Documentation updated
- [ ] Performance not degraded

## 🎉 Best Practices

1. **Write tests first** (TDD approach)
2. **Keep tests isolated** (no dependencies between tests)
3. **Use descriptive test names**
4. **Mock external services**
5. **Test both success and failure cases**
6. **Maintain test performance**
7. **Regular test maintenance**

---

## 🔗 Related Documentation

- [Django Testing Documentation](https://docs.djangoproject.com/en/stable/topics/testing/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)

Happy Testing! 🧪✨
