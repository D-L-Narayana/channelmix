Feature: Cross-channel reports
  Unified reporting across Google, Meta and Amazon.

  Scenario: Channel mix shares sum to 100%
    Given an account with 30 days of metrics
    When I request the channel-mix report
    Then every channel appears exactly once
    And the spend shares sum to 1.0
    And "google" has the best ROAS rank

  Scenario: Trend report exposes 7-day rolling averages
    Given an account with 30 days of metrics
    When I request the trend report
    Then each channel has 30 trend points
    And the 7-day average on day 7 equals the mean of the first 7 days

  Scenario: Writes invalidate cached reports for that account only
    Given an account with 30 days of metrics
    And another account with 30 days of metrics
    When I request the channel-mix report twice
    And new metrics are uploaded for the other account
    Then the channel-mix report is still served from cache
    When new metrics are uploaded for the account
    Then the channel-mix report is recomputed
