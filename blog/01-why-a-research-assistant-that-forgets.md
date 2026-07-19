# Why a research assistant that forgets

If you've played with any "AI agent with memory" demo, you've probably seen
one of two things happen. Either the agent forgets everything the moment you
close the tab — it re-asks your name every session, re-explains things
you've already told it — or it "remembers" by quietly pasting your entire
chat history back into the prompt every single time. The second one feels
more impressive at first. It's also, if you think about it for a minute, not
really memory at all. It's a bigger and bigger pile of text.

Here's the problem with the pile-of-text approach: it has no way to change
its mind. Say you tell a research assistant "the paper reports 85% accuracy"
in session one, and then in session three you say "actually, the
camera-ready version corrected that to 90%." A system that just stuffs
everything back into context now has *both* numbers sitting in there,
side by side, with nothing marking one as current and one as outdated. If
the model happens to answer with the old number, it's not really wrong from
the system's point of view — nothing ever told it that 85% stopped being
true. That's the failure mode we wanted to design around before we wrote a
single line of chat code: not "can the agent recall things," but "can the
agent tell the difference between what's still true and what used to be
true."

That reframing changes what you build first. Most memory demos start with
the chat interface and bolt memory on as a feature. We started with the
opposite question: what would it take for an agent's memory to behave like
a *careful* human assistant's memory, instead of a tape recorder? A careful
assistant doesn't remember everything you ever said with equal weight —
they remember your stated preferences longer than they remember what you
asked five minutes ago, they update their understanding when you correct
them instead of holding two contradictory beliefs at once, and they
gradually stop bringing up things that turned out not to matter. Critically,
when they *do* forget something, it's not an unexplained gap — if you ask
"didn't I tell you X," a good assistant can usually say why they let it go.

That's the actual product here: a memory layer with four kinds of memory
(what happened, what's factually true, what you prefer, and what's relevant
*right now*), a rule for resolving contradictions instead of accumulating
them, a decay policy that archives instead of silently deleting, and a
retrieval step that respects a budget instead of assuming infinite context.
The chat interface, the PDF upload, the whole "research assistant" framing
— that's the vehicle. It's what makes the memory system legible and
demoable. But if you strip the chat UI away entirely, the interesting code
is still there: four Python modules implementing write, contradiction
resolution, decay, and budgeted retrieval, each independently testable, none
of them depending on there being a chatbot attached at all.

The other half of taking this seriously was refusing to just assert that
the design is better and leaving it there. It's easy to write a memory
system and *claim* it beats the naive alternatives — dumping everything into
context, or doing plain similarity search with no notion of "this fact was
corrected." It's much more useful to actually build those naive
alternatives as real, running baselines, generate a batch of synthetic
scenarios that would expose exactly where they fail (users whose
preferences change, papers whose numbers get corrected), and measure all
three approaches side by side on the same yardstick: how often do you
retrieve the right answer, how often do you retrieve a stale one *instead*,
and how much context does it cost you to get there. That yardstick is
MemoryBench, and it's as much the point of this project as the memory layer
itself — a system that "seems to work" in a demo and a system that
*measurably* beats the obvious alternatives are different claims, and only
one of them is worth trusting with something you'll actually rely on.

The next post walks through how the four stores actually work — what gets
written, how contradictions get resolved, and the actual formula behind
"decay." The one after that gets into MemoryBench itself: what a benchmark
like this actually measures, and why "recall" alone isn't enough to trust a
memory system.
