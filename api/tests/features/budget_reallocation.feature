Feature: Budget reallocation
  Recommend moving budget toward channels with higher marginal ROAS.

  Scenario: Shift budget from a weak channel to a strong one
    Given an account with channels "google" (ROAS 4.0) and "meta" (ROAS 1.5)
    And a total daily budget of 10000.00
    When I request a budget recommendation
    Then "google" receives more budget than "meta"
    And the recommended budgets sum to 10000.00
    And every channel has an explanation mentioning marginal ROAS

  Scenario: Reports are cached
    Given an account with 30 days of metrics
    When I request the channel-mix report twice
    Then the second response is served from cache

  Scenario: Shift is capped by max_shift_pct
    Given an account with channels "google" (ROAS 4.0) and "meta" (ROAS 1.5)
    And a total daily budget of 1800.00
    When I request a budget recommendation with max shift 10%
    Then no channel moves more than 10% from its current spend
