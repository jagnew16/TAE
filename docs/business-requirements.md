# AAA Sales Assistant Agent — Business Requirements

## Context and Objective

Develop AAA, an AI-powered sales assistant, to help sales representatives improve productivity throughout the sales process—from identifying prospects and finding contacts to creating CRM leads, scheduling follow-ups, and monitoring customer activity.

Microsoft Teams will serve as the primary interface, allowing representatives to complete most routine sales tasks within one tool.

## 1. Microsoft Teams Integration

AAA should integrate with Microsoft Teams so that each sales representative can interact with it directly through a private chat.

Representatives should be able to research prospects, request market insights, manage leads, and receive reminders without frequently switching between applications.

## 2. Private Conversations and Data Access

Each representative's conversations and information shared with AAA must remain private and inaccessible to other representatives.

Access to shared company data, including CRM records, should follow the company's existing permissions and account ownership rules.

## 3. Market Intelligence and Contact Discovery

AAA should connect to third-party data sources, including BDSA and ZoomInfo, to help representatives identify suitable prospects and find relevant contacts.

### BDSA — Identify and prioritize target accounts

AAA should help representatives research:

- The top 10, 20, 30, or 50 brands in each state.
- Monthly, quarterly, and annual sales revenue.
- Leading products and product categories.
- Brand and product rankings within each state.
- Market and product trends that support prospect prioritization.

### ZoomInfo — Identify contacts and outreach channels

For selected target accounts, AAA should retrieve available contact information, including relevant decision-makers, job titles, business email addresses, and phone numbers.

Together, these sources should help representatives determine which accounts to target and how to reach them.

## 4. CRM Integration and Lead Management

AAA should integrate with the company's CRM to support duplicate checks, lead creation, and account ownership.

Before creating a lead or initiating follow-up, AAA should:

1. Check whether the prospect already exists as a customer, account, contact, or lead.
2. If the prospect is an existing customer, notify the representative and exclude it from new-prospect outreach.
3. If a matching account or lead already exists, display its status and ownership to prevent duplicate records or conflicting outreach.
4. If no matching record exists, help create a new lead and assign ownership according to company rules.

AAA should also analyze available CRM and sales data to identify product trends, purchasing patterns, and potential sales opportunities.

## 5. Follow-Up Scheduling and Reminders

AAA should help representatives schedule timely follow-ups and manage next steps.

Capabilities should include:

- Creating follow-up tasks and reminders.
- Tracking upcoming and overdue activities.
- Delivering reminders through Microsoft Teams.
- Recording follow-up activities and outcomes in the CRM.

## 6. Customer and Prospect Monitoring

AAA should monitor selected customer and prospect websites and Instagram accounts for new product launches.

When a relevant launch is detected, AAA should notify the responsible representative through Microsoft Teams, with a brief summary and a link to the source.

## 7. General-Purpose Assistance

For questions outside the sales workflows described above, AAA should use ChatGPT capabilities to provide general assistance, such as answering questions, drafting messages, summarizing information, and brainstorming ideas.

General assistance should follow the same privacy and access requirements as AAA's sales-related functions.

## Expected Business Outcomes

- Reduce time spent on manual research and administrative tasks.
- Improve prospect identification and prioritization.
- Prevent duplicate leads and conflicting account outreach.
- Increase follow-up consistency.
- Help representatives respond quickly to market changes and new product launches.

## Implementation Details to Confirm

- The CRM platform and account ownership rules.
- Available API access, licensing, and data coverage for BDSA and ZoomInfo.
- Calendar integration and reminder preferences.
- Website and Instagram monitoring scope and frequency.
- Data retention, administrative access, and privacy requirements.
