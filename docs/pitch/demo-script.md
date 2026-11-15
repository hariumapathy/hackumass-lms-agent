# Live demo script (about 2:45, Hari's real data)

Runs on **Hari's own live Canvas, Gradescope and Piazza data** (`humapathy@umass.edu`), no seeded data. Setup and the pre-demo checklist: [demo-runbook.md → Demo day](../demo-runbook.md#-demo-day-on-haris-laptop-already-set-up-your-real-data-is-in-the-local-db). **Before going on stage:** Settings shows all three sources "Updated … ago" (not Reconnect), you're signed in on **Today**, and Sessions has no test chats.

Times are targets, not hard stops. Bold lines are what you click or type; quotes are what you say.

| Time | Do | Say |
|---|---|---|
| **0:00** Hook (on Today, or a title slide) | Nothing yet | "Every UMass student lives in four tabs: Canvas, Gradescope, Piazza, email. Deadlines move, slides are scattered, and ChatGPT knows none of it. This is my real semester, live." |
| **0:20** Today | Point at **Due today / This week** (e.g. COMPSCI 335 assembly lab Monday, COMPSCI 389 in-class midterm Tuesday), then a **source chip** → the real Canvas/Gradescope page opens in a new tab → close it | "One list from all three sites, merged, with duplicates removed. Work I already submitted isn't nagging me as overdue. Every row links to the real page." |
| **0:50** Chat | Click **Chat**, type: **"Prep me for my COMPSCI 389 midterm on Tuesday: make a 5-question quiz from the lecture slides"** → Enter. Let the steps stream ("Checking your exams…", "Searching slides…") | "It's an agent with tools, but the tools only read our synced database. It never logs into Canvas itself." |
| **1:20** The answer | Point at the **Practice quiz** card, hover/click a **numbered citation** → **View** → the lecture PDF opens inside the app at the cited page → close | "Every claim cites a slide. The model only gives an ID; our code turns it into the link, so it can't make up a source." |
| **1:45** Sessions | Click **Sessions** → the chat is there with its **Practice quiz** chip → **… → Rename** → type **"389 midterm prep"** → Enter. Click the chip → answer one quiz question | "Each chat is a study session, and everything it made stays with it, ready for the night before." |
| **2:10** Calendar | Back to the chat (**Open the chat**), type: **"Add a 1-hour study session tomorrow at 3 PM for the 389 midterm"** → **Add** on the card | "It can propose, but it never writes anything without my click. Approved sessions go into my calendar feed." |
| **2:30** Close (architecture slide or just talk) | — | "A sync worker copies your classes into one database; the AI reads only that; links are verified. For UMass, this becomes an official Canvas app on campus infrastructure. One login, every class." |

## If something goes wrong
- **Answer is slow (>20 s):** keep talking over the streaming steps; that's the point of showing them.
- **Chat error:** press **Try again** once. If it fails again, skip to **Sessions** and open an existing study set made during rehearsal (keep one renamed "389 midterm prep (backup)" until after judging, then delete it).
- **No citation has View** (citation isn't a stored PDF): click it anyway; it opens the source in Canvas. Same message.
- **Signed out / Reconnect banner:** don't fix it live. Say "the live sync needs a fresh login", carry on from Sessions, fix it after.
- **Everything down:** play the recorded video.

## Rehearse once (10 minutes before)
Run the 389 quiz question and the calendar question once; if the quiz cites nothing useful, switch the course to one whose slides answered well (COMPSCI 311 or COMPSCI 335 have the most ready files). Keep that chat as the backup above and start the live demo from **New chat**.
