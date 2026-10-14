# Course-Grounded Law Study Tool

Owner: Rylan Wade  
Status: unselected alternative; no implementation. The selected project is the [Public-Company Research Assistant](../planning/PROJECT_SPEC.md).

## Product concept

A law study tool that helps students understand assigned material and build cited topic outlines, with relevant recent cases available to illustrate or challenge what they are studying. Three specialized agents interpret course sources, investigate cases, and organize the evidence. A supervisor coordinates their work and directs follow-up when the evidence is incomplete.

The core promise is: **turn a course-specific question into a useful outline whose rules, exceptions, and case comparisons can be checked against the sources.** The product's quality depends on the agents making sound decisions about evidence and relevance. Generating more text or adding more features is not the goal.

LectureBrief Law Edition is inspiration for the study problem and the emphasis on evidence. This would be a fresh project, with its own scope, materials, and implementation.

## Student and problem

The initial user is a law student studying one subject within a defined course and jurisdiction. They have assigned readings and handouts but need help connecting rules, exceptions, and cases into a coherent understanding of a topic.

The difficult work is deciding how sources relate: whether two formulations disagree, whether an exception applies, which facts explain different outcomes, and whether an outside decision is relevant to the course. A useful study outline must preserve those distinctions and make its supporting passages easy to inspect.

Recent cases have a specific role: they can give a fresh application or comparison when the student's question calls for it. They should not replace assigned cases merely because they are newer.

## Main student experience

The student chooses a topic or asks a question about the available course materials. They can request an explanation, a topic outline, or a comparison with recent decisions. The product should work from ordinary questions rather than requiring a rehearsed sequence of prompts.

1. **Ask:** identify the topic, uncertainty, and desired output. The course and jurisdiction provide context.
2. **Investigate:** the supervisor selects the relevant agents. The student can inspect which sources were consulted and why additional work was needed.
3. **Receive:** get a streamed explanation or topic outline with source links, meaningful qualifications, and visible gaps.
4. **Check:** open the exact reading passage or case passage supporting a point.
5. **Refine:** ask for a narrower outline, an explanation of an exception, or a comparison that tests an apparent contradiction. The agents revisit the evidence as needed.

The initial interface is a question input, a readable answer/outline, source passages, and an expandable activity trace. It does not need a separate outline-editing application.

## Agent responsibilities

| Role | Responsibility | Decisions it must make | Distinct capabilities |
| --- | --- | --- | --- |
| Course-material agent | Interpret assigned readings and handouts. | Identify the governing rule and qualifications; distinguish explicit support from inference; retrieve additional context when a passage is insufficient. | Search the course corpus and inspect its source/page context. |
| Recent-case agent | Investigate recent decisions relevant to the question. | Assess factual and jurisdictional relevance; identify the decision's reasoning and limits; reject weak matches; explain why a case belongs in the discussion. | Search live sources and read relevant opinions and case metadata. |
| Outline agent | Produce a cited topic outline from the gathered evidence. | Choose a hierarchy; place elements and exceptions correctly; select useful case comparisons; retain conflicts and unsupported areas; request clarification before filling a gap. | Assemble and revise structured outlines, inspect cited sources, and validate citation references. |
| Supervisor | Coordinate the work. | Decide which agents are needed, identify unresolved evidence needs, and direct bounded follow-up or return a qualified result. | Delegate work and inspect its completion and unresolved questions. |

The supervisor does not count toward the three specialized agents. Its responsibility is coordination; the outline agent owns the study artifact and the decisions about how its content is organized.

Each specialized agent needs its own prompt and meaningful tool access. Sharing a source-lookup tool is useful, but their complete tool sets and responsibilities must remain distinct.

## What reasoning should look like

An illustrative request is: "Build an outline of this topic from the readings. Find a relevant recent case, and explain whether it conflicts with the assigned rule or involves a different situation."

The course-material agent might find a general rule and then retrieve a later passage containing an exception. The recent-case agent might reject its first search result because it concerns a different jurisdiction or procedural question. The outline agent might place the selected case under the exception rather than under the general rule, or preserve an unresolved disagreement instead of merging the sources.

These are the behaviors to demonstrate. The product should expose source-backed decision summaries, selected and rejected evidence where useful, and follow-up requests. It should not present three agents repeating the same summary as meaningful collaboration.

A straightforward reading question can use the course-material agent alone. Questions requiring an outline or a recent-case comparison invoke the additional roles. Running every agent on every question would add cost without necessarily adding value.

## The outline as the main artifact

An outline is scoped to the requested topic. Depending on the material, it may contain the rule, elements, exceptions, important distinctions, assigned cases, recent-case comparisons, and unresolved questions. Each substantive point links to its supporting evidence.

The outline agent decides what belongs and how it relates. It must do more than place two summaries beneath headings. An acceptable result can state that the sources do not establish a proposition, omit an irrelevant recent case, or retain two competing formulations.

Assigned material and external developments remain distinguishable. A professor's emphasis is reported only when the available material supports it. The product does not claim an outline is complete, instructor-approved, or a determination that a case remains good law.

## Initial scope and boundaries

Start with one subject, one course context, and a defined jurisdiction. Prepare a substantive collection of original readings and handouts with enough breadth to support retrieval across several topics and competing passages. The specific course, source permissions, and corpus are still to be selected.

The first version includes course-grounded explanations, topic outlines, relevant live-case research, source inspection, and follow-up questions. Recent-case research is available when useful, not forced into every response.

Accounts, transcription, background monitoring, a full outline editor, automated grading, a practice-tutor agent, and a comprehensive legal research service are outside the initial scope. A later student pilot can extend the product based on observed needs.

## Quality and student value

Evaluate whether a student can find the rule, recognize an exception, understand why cases differ, and locate the evidence supporting an outline point. Feedback should distinguish an accurate citation from a passage that actually supports the claim.

Candidate product checks include:

- A student can open the supporting passage directly from an outline point.
- A comparison explains relevant factual or jurisdictional distinctions using the actual sources.
- An apparent contradiction triggers further investigation or a qualified conclusion.
- Missing material produces a visible gap rather than an invented rule or citation.
- A failed live search still permits a clearly bounded course-only result.
- A student can refine an outline without navigating a complex editing workflow.

Review representative outputs with a law student, TA, or instructor before treating the tool as ready for a broader student pilot. Automated retrieval metrics and model-based checks support that review; they do not establish teaching quality or legal accuracy by themselves.

## Fit with Assignment 2

This is a proposed path to meeting the assignment, not a claim that any requirement has already been implemented. The [assignment specification](../assignment/Assignment_2_Description.md) remains authoritative.

| Assignment requirement | Product fit and evidence needed |
| --- | --- |
| Three or more specialized agents, plus orchestration | Course-material and recent-case agents are distinct Research specializations; the outline agent fills the Summary role. Each needs distinct prompts and meaningful tool access. The proposed supervisor pattern uses LangGraph, with inspectable, task-driven delegation decisions and worker-failure handling. |
| Working RAG over a substantive corpus | Use LangChain LCEL for retrieval and generation over original readings and handouts, including ingestion, chunking, embeddings, Pinecone or Chroma storage, retrieval, and prompt augmentation. Answers and outlines cite original source chunks rather than relying only on previously generated summaries. |
| Live knowledge retrieval | The recent-case agent uses Tavily Remote MCP to find current decisions and inspect relevant sources. A fixed collection of downloaded cases alone would not satisfy this requirement. Any alternative must meet the assignment's live-source conditions. |
| Routing across at least two different LLM providers | Route simpler supported tasks and more demanding interpretation/comparison work according to measured cost or capability needs. Show the selected provider and rationale, and demonstrate that both providers are used. Provider choices and model IDs remain open. |
| A2A integration or MCP tool sharing | A proposed shared source-lookup MCP tool lets the course-material agent investigate evidence and the outline agent inspect that same evidence while organizing it. Both agents must actually invoke the same tool in distinct contexts, with visible evidence and a documented rationale. |
| Streaming frontend with routing, traces, and citations | A FastAPI-served vanilla HTML/JS interface streams answer tokens through SSE and makes sources, agent activity, and provider decisions inspectable. Phase updates or displaying a completed answer all at once are insufficient. |
| Public Cloud Run deployment | The application must handle arbitrary reasonable questions within its stated scope, including cold starts and partial failures. Use materials suitable for the public demonstration. If the product promises state surviving instance replacement, provide external durable persistence. |
| Evaluation | Use a fixed question set and report RAGAS faithfulness, answer relevance, context precision, and context recall. Also measure retrieval/LLM/total latency, time-to-first-token, cold versus warm behavior, cost per query, and provider comparisons. Add human review of outline quality and case relevance. |
| Submission documentation | Produce the architecture and evaluation reports, reproducible setup/deployment README, exact dependency pins, placeholder configuration, and Rylan Wade's own 200–300-word process log. This idea document is not a replacement for those deliverables. |

## Decisions before implementation

- Which subject, jurisdiction, and course context give the project a coherent boundary?
- Which substantial readings and handouts can be used in the deployed demonstration?
- Which representative questions require interpretation, comparison, and an outline rather than a single lookup?
- What makes a recent case useful to a student studying this course?
- How will the product stream useful output while clearly communicating citation/support verification status?
- Who can review the reference answers and assess whether the outlines are useful?

The direction is a focused study tool whose value comes from reasoning over evidence. Selection of this candidate and approval to implement it remain separate decisions.
