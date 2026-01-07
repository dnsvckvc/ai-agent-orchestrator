"""
Stress tests for orchestrator using Locust
Simulates 1000+ concurrent tasks with various failure scenarios
"""

import time
import random
import json
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner, WorkerRunner


class OrchestratorStressTest(HttpUser):
    """
    Stress test user simulating task submissions
    """
    wait_time = between(0.1, 0.5)  # Wait between requests

    def on_start(self):
        """Initialize user session"""
        self.task_counter = 0
        self.submitted_tasks = []

    @task(5)
    def submit_report_generation_task(self):
        """
        Submit report generation task (Use Case 1)
        Weight: 5 (50% of requests)
        """
        task_id = f"report-{self.task_counter}-{int(time.time()*1000)}"
        self.task_counter += 1

        payload = {
            "task_id": task_id,
            "task_type": "report_generation",
            "inputs": [
                {
                    "input_id": f"input-{random.randint(1, 1000)}",
                    "type": random.choice(["text", "image", "json"]),
                    "data": self._generate_random_data()
                }
                for _ in range(random.randint(1, 5))
            ],
            "execution_mode": random.choice(["sequential", "parallel", "hybrid"]),
            "priority": random.randint(1, 10),
            "timeout_ms": 30000,
            "metadata": {
                "report_title": f"Stress Test Report {task_id}",
                "user_id": f"user-{random.randint(1, 100)}"
            }
        }

        with self.client.post(
            "/api/v1/tasks",
            json=payload,
            catch_response=True,
            name="Submit Report Task"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "queued":
                    self.submitted_tasks.append(task_id)
                    response.success()
                else:
                    response.failure(f"Task not queued: {data}")
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(3)
    def submit_monitoring_task(self):
        """
        Submit real-time monitoring task (Use Case 2)
        Weight: 3 (30% of requests)
        """
        task_id = f"monitor-{self.task_counter}-{int(time.time()*1000)}"
        self.task_counter += 1

        payload = {
            "task_id": task_id,
            "task_type": "real_time_monitoring",
            "inputs": [
                {
                    "input_id": f"video-{random.randint(1, 100)}",
                    "type": "video",
                    "data": "base64_encoded_video_stream"
                }
            ],
            "execution_mode": "sequential",
            "priority": random.randint(7, 10),  # Higher priority for monitoring
            "timeout_ms": 5000,
            "metadata": {
                "max_persons": random.randint(5, 20),
                "restricted_area": random.choice([True, False])
            }
        }

        with self.client.post(
            "/api/v1/tasks",
            json=payload,
            catch_response=True,
            name="Submit Monitoring Task"
        ) as response:
            if response.status_code == 200:
                self.submitted_tasks.append(task_id)
                response.success()

    @task(2)
    def check_task_status(self):
        """
        Check status of previously submitted tasks
        Weight: 2 (20% of requests)
        """
        if not self.submitted_tasks:
            return

        task_id = random.choice(self.submitted_tasks)

        with self.client.get(
            f"/api/v1/tasks/{task_id}",
            catch_response=True,
            name="Get Task Status"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("task_id") == task_id:
                    response.success()

                    # Check latency SLA
                    if "metrics" in data:
                        latency = data["metrics"].get("total_duration_ms", 0)
                        if latency > 500:
                            events.request.fire(
                                request_type="SLA",
                                name="Latency > 500ms",
                                response_time=latency,
                                response_length=0,
                                exception=None,
                                context={}
                            )
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(1)
    def submit_api_call_task(self):
        """
        Submit API call task
        Weight: 1 (10% of requests)
        """
        task_id = f"api-{self.task_counter}-{int(time.time()*1000)}"
        self.task_counter += 1

        payload = {
            "task_id": task_id,
            "task_type": "api_call",
            "inputs": [
                {
                    "input_id": f"api-input-{random.randint(1, 1000)}",
                    "type": "json",
                    "data": {"endpoint": "https://api.example.com/data"}
                }
            ],
            "execution_mode": "parallel",
            "priority": random.randint(3, 7),
            "timeout_ms": 10000,
            "metadata": {
                "method": "POST",
                "headers": {"Content-Type": "application/json"}
            }
        }

        with self.client.post(
            "/api/v1/tasks",
            json=payload,
            catch_response=True,
            name="Submit API Task"
        ) as response:
            if response.status_code == 200:
                self.submitted_tasks.append(task_id)
                response.success()

    def _generate_random_data(self):
        """Generate random data for testing"""
        data_types = [
            {"text": f"Sample text data {random.randint(1, 10000)}"},
            {"numbers": [random.random() for _ in range(10)]},
            {"structured": {"key1": "value1", "key2": random.randint(1, 100)}}
        ]
        return random.choice(data_types)


class FailureScenarioTest(HttpUser):
    """
    Test failure scenarios
    """
    wait_time = between(0.5, 1.0)

    @task
    def submit_failing_task(self):
        """Submit tasks designed to fail"""
        task_id = f"fail-{int(time.time()*1000)}"

        payload = {
            "task_id": task_id,
            "task_type": "unknown_type",  # This should fail
            "inputs": [],
            "execution_mode": "parallel",
            "priority": 5,
            "timeout_ms": 1000,
            "metadata": {}
        }

        with self.client.post(
            "/api/v1/tasks",
            json=payload,
            catch_response=True,
            name="Submit Failing Task"
        ) as response:
            # Expect this to be handled gracefully
            if response.status_code in [200, 400, 422]:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")


# Locust event handlers for custom metrics

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Initialize custom metrics"""
    environment.stats.custom_metrics = {
        "tasks_under_500ms": 0,
        "tasks_over_500ms": 0,
        "error_count": 0,
        "total_tasks": 0
    }


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Track custom metrics"""
    if hasattr(events.request.fire, 'environment'):
        env = events.request.fire.environment

        if name == "Submit Report Task" or name == "Submit Monitoring Task":
            env.stats.custom_metrics["total_tasks"] += 1

            if response_time < 500:
                env.stats.custom_metrics["tasks_under_500ms"] += 1
            else:
                env.stats.custom_metrics["tasks_over_500ms"] += 1

        if exception:
            env.stats.custom_metrics["error_count"] += 1


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print final metrics on test completion"""
    print("\n" + "="*80)
    print("STRESS TEST RESULTS")
    print("="*80)

    stats = environment.stats

    print(f"\nTotal Requests: {stats.total.num_requests}")
    print(f"Failed Requests: {stats.total.num_failures}")
    print(f"Error Rate: {stats.total.fail_ratio * 100:.2f}%")
    print(f"Median Response Time: {stats.total.median_response_time}ms")
    print(f"95th Percentile: {stats.total.get_response_time_percentile(0.95)}ms")
    print(f"99th Percentile: {stats.total.get_response_time_percentile(0.99)}ms")
    print(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")
    print(f"RPS: {stats.total.total_rps:.2f}")

    if hasattr(environment.stats, 'custom_metrics'):
        cm = environment.stats.custom_metrics
        print(f"\nCustom Metrics:")
        print(f"Total Tasks Submitted: {cm['total_tasks']}")
        print(f"Tasks < 500ms: {cm['tasks_under_500ms']}")
        print(f"Tasks > 500ms: {cm['tasks_over_500ms']}")
        print(f"Error Count: {cm['error_count']}")

        if cm['total_tasks'] > 0:
            success_rate = ((cm['total_tasks'] - cm['error_count']) / cm['total_tasks']) * 100
            print(f"Success Rate: {success_rate:.2f}%")

    # SLA Checks
    print(f"\nSLA Compliance:")
    print(f"✓ Latency P95 < 500ms: {stats.total.get_response_time_percentile(0.95) < 500}")
    print(f"✓ Error Rate < 1%: {stats.total.fail_ratio < 0.01}")

    print("="*80 + "\n")
