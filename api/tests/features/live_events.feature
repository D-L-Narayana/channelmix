Feature: Live change feed (SSE)
  Dashboards subscribe to /stream and update without polling.

  Scenario: Metrics pushed while connected are streamed
    Given a workspace with a "google" campaign
    And a fast SSE configuration
    When I subscribe to the stream and 5 days of metrics are pushed meanwhile
    Then I receive a "ready" event followed by a "metrics.upserted" event
    And the stream closes with a reconnect hint

  Scenario: Reconnecting with Last-Event-ID replays missed events
    Given a workspace with a "google" campaign
    And a fast SSE configuration
    When the campaign is paused while I am disconnected
    And I reconnect with the Last-Event-ID of the ready event
    Then I receive exactly 1 "campaign.changed" event

  Scenario: Idempotent bulk replays do not emit duplicate events
    Given a workspace with a "meta" campaign
    When I bulk-upload 5 days of metrics with Idempotency-Key "sync-1"
    And I retry the same upload with Idempotency-Key "sync-1"
    Then the second response is marked as an idempotent replay
    And exactly 1 "metrics.upserted" event exists
