<!-- GENERATED from pcp.yaml (sha256:d8247d8141b9) by render_skill.py -- edit pcp.yaml, never this file -->

# Socratic questions

Two uses: questions PCP asks **you** when it needs something only you know, and questions it writes for
**the room** wherever the record could not answer.

## Asking the user

Ask the user only when a trigger below fires: at most 2 questions per run after setup, in one message, each skippable. Never ask what the record or the saved setup already answers. Answers are the user's own facts: tag Yours.

| When | Ask |
|---|---|
| No meeting objective in the intake | What do you want to walk out of this meeting with? |
| Two or more people match the name | Which of these is the person you're meeting? |
| The intake says you already know them, and no notes came with it | When did you last speak, and what did they tell you that isn't public? |
| You mention notes, a CRM record, a Slack or Google Chat thread, a saved LinkedIn PDF or a profile on them | Can you paste it or give me the file? I'll mark it as yours, not public. |
| Who decides, the gate or the timing is still Not determined after collection | Who else has a say in this, as far as you know? |

## Questions for the room

Every Not determined (a **Label:** line or a table cell) and every No read in the Meeting approach becomes one question to ask in the room, written in the ledger's Still open row as 'Label: question?', items separated by ' · '. Open, non-leading, one idea each; never filler. Each question starts with What, Who, How, When, Which, Where or If, and ends with a question mark.

| Kind | Use when | Example |
|---|---|---|
| Clarify | a word or priority they use but don't define | When you say {their word}, what does that look like at {organization}? |
| Assumption | the read rests on something unconfirmed | What would have to be true for {plan} to make sense this year? |
| Evidence | a fact with one weak source | What have you seen that tells you {claim}? |
| Viewpoint | who decides, or who else matters, is unknown | Who else will weigh in on {decision}, and how do they see it? |
| Consequence | urgency or timing is unknown | If nothing changes on {issue}, what happens by {date}? |
