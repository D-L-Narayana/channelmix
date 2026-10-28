Feature: Idempotent bulk metric ingestion
  Connectors push daily channel metrics in bulk; retries must never double-count.

  Scenario: Upsert on the natural key (campaign, day)
    Given a workspace with a "google" campaign
    When I bulk-upload 10 days of metrics with spend 100.00
    And I bulk-upload the same 10 days again with spend 150.00
    Then the campaign has exactly 10 metric rows
    And the total spend is 1500.00

  Scenario: Retrying with the same Idempotency-Key replays the original response
    Given a workspace with a "meta" campaign
    When I bulk-upload 5 days of metrics with Idempotency-Key "sync-2024-06-01"
    And I retry the same upload with Idempotency-Key "sync-2024-06-01"
    Then the second response is marked as an idempotent replay
    And the campaign has exactly 5 metric rows

  Scenario: Reusing an Idempotency-Key with a different payload is rejected
    Given a workspace with a "amazon" campaign
    When I bulk-upload 5 days of metrics with Idempotency-Key "sync-x"
    And I upload a different payload with Idempotency-Key "sync-x"
    Then the request is rejected with status 422
