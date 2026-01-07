"""
Script to run comprehensive stress tests and generate evaluation results
"""

import subprocess
import time
import json
import os
from datetime import datetime


class StressTestRunner:
    """
    Runs stress tests with different configurations and collects results
    """

    def __init__(self):
        self.results = {
            "test_run_id": f"stress_test_{int(time.time())}",
            "timestamp": datetime.now().isoformat(),
            "test_scenarios": []
        }

    def run_test_scenario(self, name, users, spawn_rate, duration):
        """
        Run a single stress test scenario
        """
        print(f"\n{'='*80}")
        print(f"Running Scenario: {name}")
        print(f"Users: {users}, Spawn Rate: {spawn_rate}/s, Duration: {duration}s")
        print(f"{'='*80}\n")

        cmd = [
            "locust",
            "-f", "tests/stress/locustfile.py",
            "--headless",
            "--users", str(users),
            "--spawn-rate", str(spawn_rate),
            "--run-time", f"{duration}s",
            "--host", "http://localhost:8000",
            "--html", f"tests/stress/results/{name}_report.html",
            "--csv", f"tests/stress/results/{name}",
            "--only-summary"
        ]

        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=duration + 60
            )

            duration_actual = time.time() - start_time

            scenario_result = {
                "name": name,
                "users": users,
                "spawn_rate": spawn_rate,
                "planned_duration": duration,
                "actual_duration": duration_actual,
                "success": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr
            }

            # Parse results from stdout
            self._parse_output(scenario_result, result.stdout)

            self.results["test_scenarios"].append(scenario_result)

            print(f"\nScenario '{name}' completed in {duration_actual:.2f}s")

            return scenario_result

        except subprocess.TimeoutExpired:
            print(f"ERROR: Scenario '{name}' timed out!")
            scenario_result = {
                "name": name,
                "users": users,
                "spawn_rate": spawn_rate,
                "planned_duration": duration,
                "success": False,
                "error": "Timeout"
            }
            self.results["test_scenarios"].append(scenario_result)
            return scenario_result

    def _parse_output(self, scenario_result, output):
        """Parse metrics from Locust output"""
        lines = output.split('\n')

        metrics = {
            "total_requests": 0,
            "failed_requests": 0,
            "error_rate_percent": 0.0,
            "median_ms": 0,
            "p95_ms": 0,
            "p99_ms": 0,
            "avg_ms": 0.0,
            "rps": 0.0
        }

        for line in lines:
            if "Total Requests:" in line:
                metrics["total_requests"] = int(line.split(":")[-1].strip())
            elif "Failed Requests:" in line:
                metrics["failed_requests"] = int(line.split(":")[-1].strip())
            elif "Error Rate:" in line:
                metrics["error_rate_percent"] = float(line.split(":")[-1].strip().replace("%", ""))
            elif "Median Response Time:" in line:
                metrics["median_ms"] = float(line.split(":")[-1].strip().replace("ms", ""))
            elif "95th Percentile:" in line:
                metrics["p95_ms"] = float(line.split(":")[-1].strip().replace("ms", ""))
            elif "99th Percentile:" in line:
                metrics["p99_ms"] = float(line.split(":")[-1].strip().replace("ms", ""))
            elif "Average Response Time:" in line:
                metrics["avg_ms"] = float(line.split(":")[-1].strip().replace("ms", ""))
            elif "RPS:" in line:
                metrics["rps"] = float(line.split(":")[-1].strip())

        scenario_result["metrics"] = metrics

    def run_all_scenarios(self):
        """
        Run comprehensive stress test scenarios
        """
        print("\n" + "="*80)
        print("COMPREHENSIVE STRESS TEST SUITE")
        print("="*80)

        # Create results directory
        os.makedirs("tests/stress/results", exist_ok=True)

        # Scenario 1: Baseline - moderate load
        self.run_test_scenario(
            name="baseline_moderate",
            users=100,
            spawn_rate=10,
            duration=60
        )

        time.sleep(5)  # Cool down

        # Scenario 2: High load
        self.run_test_scenario(
            name="high_load",
            users=500,
            spawn_rate=50,
            duration=120
        )

        time.sleep(5)

        # Scenario 3: Extreme load (1000+ concurrent)
        self.run_test_scenario(
            name="extreme_load",
            users=1000,
            spawn_rate=100,
            duration=180
        )

        time.sleep(5)

        # Scenario 4: Spike test
        self.run_test_scenario(
            name="spike_test",
            users=2000,
            spawn_rate=500,
            duration=60
        )

        time.sleep(5)

        # Scenario 5: Endurance test
        self.run_test_scenario(
            name="endurance_test",
            users=300,
            spawn_rate=30,
            duration=300
        )

    def generate_report(self):
        """
        Generate comprehensive evaluation report
        """
        print("\n" + "="*80)
        print("GENERATING EVALUATION REPORT")
        print("="*80)

        # Calculate aggregate metrics
        self.results["aggregate_metrics"] = self._calculate_aggregate_metrics()

        # Check SLA compliance
        self.results["sla_compliance"] = self._check_sla_compliance()

        # Save results to JSON
        report_path = f"tests/stress/results/evaluation_report_{self.results['test_run_id']}.json"
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"\nEvaluation report saved to: {report_path}")

        # Print summary
        self._print_summary()

    def _calculate_aggregate_metrics(self):
        """Calculate aggregate metrics across all scenarios"""
        total_requests = sum(
            s.get("metrics", {}).get("total_requests", 0)
            for s in self.results["test_scenarios"]
        )

        total_failures = sum(
            s.get("metrics", {}).get("failed_requests", 0)
            for s in self.results["test_scenarios"]
        )

        avg_error_rate = sum(
            s.get("metrics", {}).get("error_rate_percent", 0)
            for s in self.results["test_scenarios"]
        ) / len(self.results["test_scenarios"]) if self.results["test_scenarios"] else 0

        avg_p95 = sum(
            s.get("metrics", {}).get("p95_ms", 0)
            for s in self.results["test_scenarios"]
        ) / len(self.results["test_scenarios"]) if self.results["test_scenarios"] else 0

        return {
            "total_requests": total_requests,
            "total_failures": total_failures,
            "average_error_rate_percent": avg_error_rate,
            "average_p95_latency_ms": avg_p95,
            "scenarios_passed": sum(1 for s in self.results["test_scenarios"] if s.get("success", False)),
            "scenarios_total": len(self.results["test_scenarios"])
        }

    def _check_sla_compliance(self):
        """Check SLA compliance"""
        agg = self.results.get("aggregate_metrics", {})

        compliance = {
            "latency_p95_under_500ms": agg.get("average_p95_latency_ms", float('inf')) < 500,
            "error_rate_under_1_percent": agg.get("average_error_rate_percent", 100) < 1.0,
            "all_scenarios_passed": agg.get("scenarios_passed", 0) == agg.get("scenarios_total", -1)
        }

        compliance["overall_pass"] = all(compliance.values())

        return compliance

    def _print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("STRESS TEST SUMMARY")
        print("="*80)

        agg = self.results["aggregate_metrics"]
        sla = self.results["sla_compliance"]

        print(f"\nAggregate Metrics:")
        print(f"  Total Requests: {agg['total_requests']}")
        print(f"  Total Failures: {agg['total_failures']}")
        print(f"  Average Error Rate: {agg['average_error_rate_percent']:.2f}%")
        print(f"  Average P95 Latency: {agg['average_p95_latency_ms']:.2f}ms")
        print(f"  Scenarios Passed: {agg['scenarios_passed']}/{agg['scenarios_total']}")

        print(f"\nSLA Compliance:")
        print(f"  ✓ Latency P95 < 500ms: {'PASS' if sla['latency_p95_under_500ms'] else 'FAIL'}")
        print(f"  ✓ Error Rate < 1%: {'PASS' if sla['error_rate_under_1_percent'] else 'FAIL'}")
        print(f"  ✓ All Scenarios Passed: {'PASS' if sla['all_scenarios_passed'] else 'FAIL'}")

        print(f"\n  Overall SLA Compliance: {'PASS ✓' if sla['overall_pass'] else 'FAIL ✗'}")

        print("\n" + "="*80)


def main():
    """Main entry point"""
    runner = StressTestRunner()

    try:
        runner.run_all_scenarios()
        runner.generate_report()

        print("\n✓ Stress testing complete!")
        print("  Check tests/stress/results/ for detailed reports")

    except KeyboardInterrupt:
        print("\n\nStress test interrupted by user")
        runner.generate_report()

    except Exception as e:
        print(f"\n\nERROR during stress testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
