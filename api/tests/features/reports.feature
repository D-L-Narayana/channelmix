Feature: Cross-channel reports
  Unified reporting across Google, Meta, Amazon, LinkedIn and other channels, scoped to a workspace.

  Scenario: Channel mix shares sum to 100%
    Given a workspace with 30 days of metrics
    When I request the channel-mix report
    Then every channel appears exactly once
    And the spend shares sum to 1.0
    And "google" has the best ROAS rank

  Scenario: Trend report exposes 7-day rolling averages
    Given a workspace with 30 days of metrics
    When I request the trend report
    Then each channel has 30 trend points
    And the 7-day average on day 7 equals the mean of the first 7 days

  Scenario: Writes invalidate cached reports for that workspace only
    Given a workspace with 30 days of metrics
    And another workspace with 30 days of metrics
    When I request the channel-mix report twice
    And new metrics are uploaded for the other workspace
    Then the channel-mix report is still served from cache
    When new metrics are uploaded for the workspace
    Then the channel-mix report is recomputed
