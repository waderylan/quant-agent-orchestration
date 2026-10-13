# Ski Road-Trip Planner for the United States and Canada

Owner: Rylan Wade  
Status: candidate idea; not selected for implementation.  
Deadline planning assumption: October 29, 2026, as supplied by Rylan Wade.

## Product concept

A ski road-trip planner that turns a skier's dates, starting point, pass, budget, terrain preferences, and driving tolerance into a researched itinerary across US and Canadian destinations. The plan explains why each stop belongs, what tradeoffs it makes, and which facts or assumptions could change it.

The central promise is: **choose the right mix of ski resorts and allocate the trip's ski days using resort facts, skier experiences, and the group's preferences.** Three specialized agents interpret resort data, investigate reviews, and construct the ski itinerary. A supervisor directs their work and resolves missing information.

Weather and resort reviews contribute to the decisions. They should influence a plan when relevant without becoming unsupported predictions or replacing official operating information.

Driving estimates come from an existing routing service or explicit user input. The product uses those estimates as constraints; developing navigation, traffic prediction, or a maps agent is outside its scope.

## Who it serves

The target users are skiers in the United States and Canada planning trips within either country or across the border. They may already own a pass, have a limited number of vacation days, travel with a mixed-ability group, or want to balance skiing with reasonable driving and accommodation costs.

The product should handle origins and destinations in both countries, local time zones, metric and imperial units, and USD/CAD budgets. Each displayed price retains its original currency; converted estimates identify the conversion date and assumptions. Cross-border legs are visible rather than disappearing inside a driving estimate.

Broad US/Canada usability is the product goal. The first demonstration needs an explicit coverage boundary, with representative destinations in both countries. Unsupported resorts or corridors must be identified as coverage gaps. A continent-wide launch is not an assumption behind the assignment version.

## The problem

A resort can look attractive in isolation and still be a poor addition to a ski trip. Its terrain may not suit the group, the pass may provide limited access, or reviews may describe an experience different from the resort's marketing. Two highly rated resorts may offer nearly the same experience, while a less famous stop might better complement the trip. Reports and reviews may describe different seasons, conditions, or skier preferences.

The product opportunity is to explain which resorts deserve a place on this skier's trip, how many ski days each deserves, and why. The student-project opportunity is to demonstrate agents resolving conflicting evidence and changing those choices when preferences or information change.

## Main experience

1. **Describe the trip:** provide dates, origin and return point, pass type and season, budget currency, skiing preferences, group needs, and acceptable driving. Identify must-visit destinations and whether dates are flexible.
2. **Compare possibilities:** receive resort combinations with evidence about terrain fit, access, skier experience, variety, and compromises. Ask a short clarification only when missing information would materially change the choices.
3. **Inspect the itinerary:** see the daily sequence of travel, skiing, and overnight locations, together with sources and assumptions.
4. **Challenge a decision:** ask why a destination was excluded, what happens with a lower budget, or whether another ski day is worth an additional move. The agents revisit the relevant evidence and calculations.
5. **Refresh before departure:** check available forecasts and official resort updates relevant to the actual dates. Explain whether new information changes the selected resorts or ski-day allocation.

The initial interface is a streaming conversation with resort comparisons, a readable day-by-day ski plan, and expandable evidence and agent activity. It can show externally supplied driving estimates and links to an existing maps service. A custom interactive map is outside the initial scope.

## Three reasoning agents and a supervisor

| Role | Responsibility | Decisions it must make | Distinct capabilities |
| --- | --- | --- | --- |
| Resort data agent | Establish what each resort offers and whether it fits the skier's dates and pass. | Compare terrain mix and mountain zones against group preferences; apply season-specific access rules; identify missing or conflicting resort facts; interpret available weather and operating information. | Query structured resort/pass records, retrieve original official documents, and look up current resort updates and weather. |
| Resort review agent | Understand the experience skiers report and how relevant it is to this group. | Identify specific strengths and drawbacks; distinguish editorial assessments from guest anecdotes; explain conflicting reviews using stated ability, conditions, and dates; investigate claims that disagree with official information. | Retrieve and compare permitted review material, examine review provenance/date/context, and verify factual claims through shared resort/source lookup. |
| Ski itinerary agent | Choose the resort combination and produce the trip artifact. | Select complementary destinations; allocate ski days; balance documented fit, review evidence, pass access, and supplied travel constraints; request clarification; explain selected and excluded options. | Build and revise structured itineraries, compare candidate combinations, and validate ski-day, pass, and trip constraints using source-backed findings. |
| Supervisor | Coordinate investigation. | Select the agents needed, direct bounded follow-up, and handle incomplete results or worker failures. | Delegate tasks and track outstanding questions and completion. |

The supervisor owns coordination. The ski itinerary agent owns resort selection, ski-day allocation, and the final plan. The supervisor is not a fourth specialized worker for grading purposes.

The agents' substantive work is about ski resorts and skier experiences. Weather and pass information inform that work. Routine driving estimates and arithmetic are supporting tools, not separate reasoning agents.

## What meaningful reasoning looks like

An illustrative request is: "Plan an eight-day ski road trip with my existing pass. We have intermediate and advanced skiers, want two resorts with different experiences, and care more about enjoyable terrain than nightlife. Explain which resorts deserve more of our ski days."

In a hypothetical comparison, the resort data agent finds that two candidates advertise substantial intermediate terrain. The review agent finds that the available reviews distinguish them: one is described as convenient for mixed groups, while another draws praise mainly for expert terrain. It checks the context and looks for corroboration instead of treating those descriptions as universal facts. The ski itinerary agent may allocate more days to the mixed-group option, pair it with a genuinely different second resort, or request further evidence before choosing.

Review analysis must go beyond averaging stars. A low rating caused by nightlife may be irrelevant to this group; a repeated, well-supported concern about convenient access to suitable terrain may matter. The agents should explain those distinctions, retain disagreements, and identify when the sample cannot support a strong conclusion.

When the trip enters a usable forecast window, weather can change the order or justify a contingency. Months beforehand, the same question should produce a plan with explicit weather uncertainty rather than invented snow predictions.

## The final trip artifact

A useful plan includes:

- Day-by-day destinations, ski days, transfer days, and overnight areas.
- Supporting driving estimates from an existing route service or the user, with their assumptions visible.
- Resort comparisons explaining terrain fit, variety between stops, ski-day allocation, and applicable pass/access rules for the requested dates and season.
- A budget breakdown separating sourced prices, calculated estimates, and user-supplied assumptions, with currencies visible.
- Relevant review themes and their source dates, kept distinct from official facts.
- Weather context appropriate to the planning horizon and timestamps on current information.
- An alternate resort combination, plus the preferences or new evidence that would make it preferable.
- Source links and unresolved information that materially affects feasibility.

The first version recommends a plan. It does not book accommodation, buy passes, promise road conditions, or monitor the trip continuously.

## Corpus and source strategy

The reference corpus should be a substantial collection of original resort documents and permitted review material across supported destinations. It needs enough depth to compare terrain, access, mountain experience, and preference-dependent tradeoffs. A handful of resort statistics or scraped star ratings would not demonstrate the required retrieval structure.

| Source category | Material to collect | Product use |
| --- | --- | --- |
| Official resort documents | Terrain and mountain-zone guides, visitor FAQs, lessons/rentals information, parking, shuttle, accessibility, and operating policies. | Explain suitability and practical constraints. |
| Pass-provider documents | Season-specific destination access, blackout dates, reservation requirements, and shared day limits. | Determine whether the proposed ski dates fit the user's exact pass. |
| Destination and transportation guides | Tourism-board guides, lodging-area descriptions, regional transport information, and winter-access documentation. | Compare overnight bases and travel logistics. |
| Independent resort assessments | Substantive editorial reviews and permitted skier-review material, with author/date context and expressed skier preferences where available. | Identify preference-dependent strengths and drawbacks, explain conflicting experiences, and investigate claims needing corroboration. |
| Historical climate material | Official climate documentation and relevant station summaries. | Explain seasonal context while preserving the distinction from a forecast. |

A provisional collection target is 6–10 supported resorts across both countries, with roughly 6–10 substantive documents per resort plus shared pass and regional material. This is a planning target, not a grading threshold or a claim that those documents have been collected. Expand based on retrieval gaps and useful route coverage rather than raw page count.

Trail maps and statistics can support structured tools; image-only maps and duplicated navigation text should not pad the RAG corpus. Preserve source URL, resort, country, language, applicable season, publication date where available, and collection time. Retain conflicting versions with their applicability rather than silently blending them.

## Collection: APIs and targeted scrapers

Many sources will be needed, but the first release should collect the highest-value resort and review material deliberately. Prefer documented APIs or feeds for structured resort information, weather, and exchange rates. Use targeted scrapers for permitted resort, tourism, pass-policy, and review pages when an appropriate feed is unavailable. Obtain driving estimates from an existing provider rather than collecting road-network data or developing navigation.

The collection process should preserve useful text and source context, remove duplicates, flag missing or changed content, and record whether material can be stored and displayed in the deployed product. Respect source terms and access limits; a public page is not automatically an unrestricted review dataset. In particular, [Google Places policies](https://developers.google.com/maps/documentation/places/web-service/policies) restrict caching/storage and require attribution, so its content is not assumed suitable for a permanent bulk-review corpus.

Stable guides can be refreshed periodically. Season-specific policies and reviews need applicability checks. Weather, availability, prices, and operating status need freshness appropriate to the decision; retrieval from an old snapshot does not establish their current state. Missing live information should remain visible, with a bounded result rather than an invented replacement.

Scraping is a means of assembling evidence. The main project remains agent reasoning and itinerary construction, not building a general-purpose crawler.

## Weather and reviews

For US destinations, the [National Weather Service API](https://www.weather.gov/documentation/services-web-api) offers forecasts, alerts, and observations, with its listed forecast endpoints covering the next seven days. For Canadian destinations, [Meteorological Service of Canada open-data documentation](https://eccc-msc.github.io/open-data/) describes available data and access services. The usable forecast horizon must be checked for the selected product.

Use location and elevation context rather than treating a nearby town's weather as an exact mountain forecast. Keep predicted snowfall, observations, and confirmed resort operations separate. Long-range planning can use historical context; it must not claim to know the actual snow or open terrain for a future trip.

Reviews are preference evidence. Extract specific themes such as convenience, terrain fit, family experience, or lodging atmosphere, with dates and source links. Distinguish editorial judgment from guest reports, avoid implying that a small sample is representative, and corroborate operational claims with official sources. Reviews do not override closures or access rules.

## US and Canadian source candidates

These are researched starting points, not completed integrations or confirmation that all needed content is available for bulk collection:

- [Mammoth visitor guide](https://www.mammothmountain.com/discover-mammoth/winter-first-timers-guide) and [Palisades visitor guides](https://www.palisadestahoe.com/explore/first-timers-guide): US resort reference material.
- [Whistler Blackcomb vacation guide](https://www.whistlerblackcomb.com/travel-guide/vacation-faqs.aspx) and [Tourism Whistler trip planning](https://www.whistler.com/plan/): Canadian resort/destination reference material.
- [Ikon pass comparison](https://www.ikonpass.com/en/compare-passes) and [Epic restricted dates](https://www.epicpass.com/info/peak-restricted-dates.aspx): access-policy candidates; retain season and pass-specific applicability.
- [NWS API](https://www.weather.gov/documentation/services-web-api) and [MSC open data](https://eccc-msc.github.io/open-data/): weather-source candidates for both countries.
- [Bank of Canada Valet API](https://www.bankofcanada.ca/valet/docs): a candidate for dated currency-conversion estimates, not a promise of the rate a traveler will pay.
- [OnTheSnow resort reviews](https://www.onthesnow.com/california/mammoth-mountain-ski-area/reviews): an example of skier-review content; collection and reuse remain subject to the source's terms.

US/Canada coverage also requires a supporting route provider for driving estimates. The product links out for navigation and current road details; it does not build its own maps or road-monitoring system.

## Fit with Assignment 2

This is a proposed path to meeting the [assignment specification](../assignment/Assignment_2_Description.md), not evidence that any requirement is implemented.

| Requirement | Proposed fit and evidence |
| --- | --- |
| Three specialized agents and orchestration | Resort data fills the Data role with structured resort/pass queries plus documentary retrieval, review investigation fills the Research role, and ski itinerary generation fills the Summary role. Distinct prompts and tools support substantive specialization. A proposed LangGraph supervisor makes task-driven decisions and handles worker failures. |
| Substantive RAG | Use LangChain LCEL over ingested, chunked, embedded source documents stored in Pinecone or Chroma. Retrieve context for decisions and cite original chunks in explanations and itineraries. |
| Live retrieval | Use Tavily Remote MCP for current resort announcements, policy changes, and review/source research. Weather APIs supplement it; they are not assumed to replace the assignment's specified live-knowledge path. |
| Two different generation providers | Route tasks according to cost/capability needs, with visible reasons and actual use of both providers. Select and verify providers/model IDs later. |
| A2A or shared MCP tools | Expose shared resort/source lookup or itinerary-constraint tools through MCP. Different agents must invoke the same tool in different contexts, with the calls and rationale inspectable. |
| Streaming interface | FastAPI serves a vanilla HTML/JS chat and SSE answer tokens, with visible routing decisions, agent traces, and linked citations. Phase updates alone are insufficient. |
| Cloud Run | Deploy an application that handles arbitrary reasonable questions within declared coverage. Demonstrate cold-start behavior and partial failures. External durable state is required only if persistence across instance replacement is promised. |
| Evaluation and submission | Report fixed-question-set RAGAS metrics, retrieval/LLM/total latency, TTFT, cold/warm behavior, per-query costs, and provider comparisons. Include the required architecture report, README, exact dependency pins, placeholder configuration, source archive, and Rylan Wade's own process log. |

## Deadline and scope

The October 29 deadline makes future-trip planning more practical than an application that depends on live winter lift operations. A demonstration can use current season policies and announcements while planning later ski dates. It should not present October weather as evidence of January conditions.

Prioritize a coherent supported resort set in both countries, substantive resort and review documents, three working agents, and a cited itinerary that explains resort selection and ski-day allocation. Tests should include US-only, Canada-only, and cross-border cases where coverage supports them. Broader resort coverage, booking, accommodation inventory, and continuous alerts can follow later. Navigation remains delegated to an existing service.

The product must expose coverage limitations. Supporting US and Canadian skiers means treating both countries as first-class contexts; it does not mean claiming every resort is supported at submission.

## Quality and open decisions

Evaluate whether selected resorts match the skier's stated preferences and group needs, whether review claims are supported and appropriately qualified, and whether ski-day allocation reflects meaningful differences between destinations. Check date/pass constraints, supplied driving limits, available days, units, and currencies as supporting feasibility conditions. Include conflicting reviews, outdated policies, unavailable forecasts, inaccessible sources, and preference changes that should alter the resort selection. A strong example shows new evidence changing the itinerary and explains why.

Before implementation, select the initial resorts, verify review access and document depth, define which resort attributes and review themes matter, and identify feasible live feeds. Choose a supporting driving-estimate source and define reference comparisons and itineraries for evaluation. Decide whether French-language output is part of the first release and how original source language will be preserved.

The candidate is promising if the agents explain which resorts fit this skier, resolve competing evidence, and turn those decisions into a feasible trip. Generic resort rankings, star-rating summaries, or a navigation-first itinerary would not meet that product standard.
