from requests.exceptions import ConnectionError, HTTPError, InvalidURL, Timeout
from simplejson import JSONDecodeError

from datadog_checks.base import AgentCheck, ConfigurationError

SCALR_DD_METRICS_ENDPOINT = "{}/api/iacp/v3/integrations/datadog/account/{}/metrics"
SCALR_URL_PARAM = "url"
SCALR_ACCOUNT_ID_PARAM = "account_id"
SCALR_ACCESS_TOKEN_PARAM = "access_token"


class ScalrCheck(AgentCheck):

    __NAMESPACE__ = "scalr"

    SERVICE_CHECK_NAME = "can_connect"

    SCALR_ACCOUNT_METRICS = {
        "environments-count": "environments.count",
        "workspaces-count": "workspaces.count",
        "runs-count": "runs.count",
        "runs-successful": "runs.successful",
        "runs-failed": "runs.failed",
        "runs-awaiting-confirmation": "runs.awaiting_confirmation",
        "runs-concurrency": "runs.concurrency",
        "runs-queue-size": "runs.queue_size",
        "quota-max-concurrency": "quota.max_concurrency",
        "billings-runs-count": "billing.runs.count",
        "billings-run-minutes-count": "billing.run_minutes.count",
        "billings-flex-runs-count": "billing.flex_runs.count",
        "billings-flex-runs-minutes-count": "billing.flex_run_minutes.count",
    }

    def check(self, instance):

        self._validate_instance(instance)

        try:
            response = self.http.get(
                SCALR_DD_METRICS_ENDPOINT.format(instance[SCALR_URL_PARAM], instance[SCALR_ACCOUNT_ID_PARAM]),
                extra_headers=self._get_extra_headers(instance),
                timeout=60,
            )
            response.raise_for_status()
            response_json = response.json()

            for key, name in self.SCALR_ACCOUNT_METRICS.items():
                if key in response_json and response_json[key] is not None:
                    self.gauge(name, response_json[key], tags=instance.get('tags', []))

        except Timeout as e:
            self.service_check(
                self.SERVICE_CHECK_NAME,
                AgentCheck.CRITICAL,
                message="Request timeout: {}, {}".format(instance[SCALR_URL_PARAM], e),
            )
            self.log.exception("Communication with Scalr timed out.", e)

        except (HTTPError, InvalidURL, ConnectionError) as e:
            self.service_check(
                self.SERVICE_CHECK_NAME,
                AgentCheck.CRITICAL,
                message="Request failed: {}, {}".format(instance[SCALR_URL_PARAM], e),
            )
            self.log.exception("Couldn't reach Scalr.", e)

        except JSONDecodeError as e:
            self.service_check(
                self.SERVICE_CHECK_NAME,
                AgentCheck.CRITICAL,
                message="JSON Parse failed: {}, {}".format(instance[SCALR_URL_PARAM], e),
            )
            self.log.exception("Unexpected response from Scalr.", e)

        except ValueError as e:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, message=str(e))
            self.log.exception(e)

    @staticmethod
    def _validate_instance(instance):
        """
        Validate that all required parameters are present in the instance.
        """
        missing = []
        for option in ("url", "account_id", "access_token"):
            if option not in instance:
                missing.append(option)

        if missing:
            missing = ", ".join(missing)
            raise ConfigurationError("Scalr instance configuration missing option(s): {}".format(missing))

    @staticmethod
    def _get_extra_headers(instance):
        return {
            "Accept": "application/json",
            "Authorization": "Bearer {}".format(instance[SCALR_ACCESS_TOKEN_PARAM]),
            "Prefer": "profile=internal",
        }
