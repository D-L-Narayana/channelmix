Feature: Budget reallocation
  Recommend moving budget toward channels with higher marginal ROAS.

  Scenario: Shift budget from a weak channel to a strong one
    Given an account with channels "google" (ROAS 4.0) and "meta" (ROAS 1.5)
    And a total daily budget of 10000.00
    When I request a budget recommendation
    Then "google" receives more budget than "meta"
    And the recommended budgets sum to 10000.00

  Scenario: Reports are cached
    Given an account with 30 days of metrics
    When I request the channel-mix report twice
    Then the second response is served from cache
