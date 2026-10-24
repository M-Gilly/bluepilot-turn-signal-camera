import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace, ModuleType
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('diagnostic', Path(__file__).resolve().parents[1]/'diagnose_ford_tests.py')
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


class Tests(unittest.TestCase):
  def result(self, fail=False, hook=1):
    result = diagnostic.RecordedResult()
    case = unittest.FunctionTestCase(lambda: None, description='fixed test')
    fake_numpy = SimpleNamespace(random=SimpleNamespace(seed=lambda value: None))
    with patch.dict(sys.modules, numpy=fake_numpy):
      result.startTest(case)
    result.event('hook', 'safety_tx_hook', [1, 0, '00'], hook)
    if fail:
      try:
        case.assertEqual(False, True)
      except AssertionError:
        result.addFailure(case, sys.exc_info())
    else:
      result.addSuccess(case)
    result.stopTest(case)
    return result

  def report(self, fail=False, hook=1):
    result = self.result(fail, hook)
    row = result.rows[0]
    totals = {key: row[key] * 571 for key in ('failures','errors','skipped','expected_failures','unexpected_successes','hook_calls')}
    return dict(cases=571, totals=totals, rows=[dict(row) for _ in range(571)])

  def test_identical_existing_failures_match(self):
    self.assertEqual(diagnostic.compare(self.report(True), self.report(True)), [])

  def test_different_failure_cannot_be_hidden(self):
    self.assertTrue(diagnostic.compare(self.report(True), self.report(False)))

  def test_different_hook_with_identical_pass_is_detected(self):
    self.assertTrue(diagnostic.compare(self.report(hook=0), self.report(hook=1)))

  def test_incomplete_suite_rejected(self):
    a=self.report(); b=self.report(); a['cases']=570
    self.assertTrue(diagnostic.compare(a,b))

  def test_errors_rejected_even_when_identical(self):
    a=self.report(); a['totals']['errors']=1
    self.assertTrue(diagnostic.compare(a,a))

  def test_subtest_success_and_failure_both_recorded(self):
    result=diagnostic.RecordedResult();case=unittest.FunctionTestCase(lambda:None)
    fake_numpy=SimpleNamespace(random=SimpleNamespace(seed=lambda value:None))
    with patch.dict(sys.modules,numpy=fake_numpy):result.startTest(case)
    result.addSubTest(case,case,None)
    before=result.trace.hexdigest()
    result.addSubTest(case,case,None)
    self.assertNotEqual(before,result.trace.hexdigest())
    try:case.assertEqual(0,1)
    except AssertionError:result.addSubTest(case,case,sys.exc_info())
    self.assertEqual(result.current['failures'],1)
    result.stopTest(case)
    self.assertEqual(len(result.rows),1)

  def run_suite(self, suite, modules=None):
    result=diagnostic.RecordedResult()
    fake_numpy=SimpleNamespace(random=SimpleNamespace(seed=lambda value:None))
    with patch.dict(sys.modules,dict(modules or {},numpy=fake_numpy)):
      suite.run(result)
    return result

  def test_real_suite_class_skip_then_normal_test(self):
    class Skipped(unittest.TestCase):
      @classmethod
      def setUpClass(cls):raise unittest.SkipTest('abstract base')
      def test_unused(self):raise AssertionError('must not run')
    class Active(unittest.TestCase):
      def test_pass(self):pass
    loader=unittest.TestLoader()
    result=self.run_suite(unittest.TestSuite([loader.loadTestsFromTestCase(Skipped),loader.loadTestsFromTestCase(Active)]))
    self.assertEqual(result.testsRun,1)
    self.assertEqual(len(result.rows),1)
    self.assertEqual(result.rows[0]['skipped'],0)
    self.assertEqual(result.fixture_events[0]['kind'],'skipped')
    self.assertEqual(result.fixture_events[0]['reason'],'abstract base')

  def test_real_suite_class_setup_error_recorded(self):
    class Broken(unittest.TestCase):
      @classmethod
      def setUpClass(cls):raise RuntimeError('setup failed')
      def test_unused(self):raise AssertionError('must not run')
    result=self.run_suite(unittest.TestLoader().loadTestsFromTestCase(Broken))
    self.assertEqual(result.testsRun,0)
    self.assertEqual(result.fixture_events[0]['kind'],'errors')
    self.assertEqual(result.fixture_events[0]['message'],'setup failed')

  def test_real_suite_class_teardown_error_recorded(self):
    class Broken(unittest.TestCase):
      @classmethod
      def tearDownClass(cls):raise RuntimeError('teardown failed')
      def test_pass(self):pass
    result=self.run_suite(unittest.TestLoader().loadTestsFromTestCase(Broken))
    self.assertEqual(result.testsRun,1)
    self.assertEqual(result.fixture_events[0]['kind'],'errors')
    self.assertEqual(result.fixture_events[0]['message'],'teardown failed')

  def test_real_suite_module_skip_recorded(self):
    module=ModuleType('_diagnostic_fixture_test')
    def setup():raise unittest.SkipTest('module unavailable')
    module.setUpModule=setup
    case=type('Example',(unittest.TestCase,),{'__module__':module.__name__,'test_unused':lambda self:None})
    result=self.run_suite(unittest.TestLoader().loadTestsFromTestCase(case),{module.__name__:module})
    self.assertEqual(result.testsRun,0)
    self.assertEqual(result.fixture_events[0]['kind'],'skipped')
    self.assertEqual(result.fixture_events[0]['reason'],'module unavailable')

  def test_real_suite_individual_skip_still_counted(self):
    class Skipped(unittest.TestCase):
      @unittest.skip('individual skip')
      def test_unused(self):pass
    result=self.run_suite(unittest.TestLoader().loadTestsFromTestCase(Skipped))
    self.assertEqual(result.testsRun,1)
    self.assertEqual(result.rows[0]['skipped'],1)
    self.assertEqual(result.fixture_events,[])

  def test_changed_fixture_reason_rejected(self):
    a=self.report();b=self.report()
    a['fixture_events']=[dict(kind='skipped',test='setUpClass',reason='first')]
    b['fixture_events']=[dict(kind='skipped',test='setUpClass',reason='different')]
    self.assertTrue(diagnostic.compare(a,b))


if __name__ == '__main__':
  unittest.main()
