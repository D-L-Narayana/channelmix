Feature: Workspace isolation
  Every workspace is a tenant identified by its API key. Data never leaks between tenants.

  Scenario: Creating a workspace returns the API key exactly once
    When I create a workspace "Acme Retail" with email "owner@acme-example.com"
    Then the response contains an API key and a slug
    And the API key is not returned by GET /workspaces/me

  Scenario: Requests without a valid API key are rejected
    Given a workspace with a "google" campaign
    When I call the campaigns endpoint without an API key
    Then the request is rejected with status 401
    When I call the campaigns endpoint with a forged API key
    Then the request is rejected with status 401

  Scenario: Another workspace cannot see or modify my campaigns
    Given a workspace with a "google" campaign
    And another workspace
    When the other workspace reads my campaign
    Then the request is rejected with status 404
    When the other workspace pushes metrics for my campaign
    Then the request is rejected with status 422
    And my campaign still has 0 metric rows

  Scenario: Reports and events are scoped to the workspace
    Given a workspace with 30 days of metrics
    And another workspace with 30 days of metrics
    When I request the channel-mix report
    Then every channel appears exactly once
    And the other workspace sees only its own channels
    And the other workspace sees none of my events
