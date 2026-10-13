# Quant Agent Orchestration

Rylan Wade · CSCI 599, USC

Company research means moving between long reports, financial figures, and current news. I'm building a research assistant that brings those sources together so a user can ask what changed in a company and check whether the numbers support the explanation.

The planned system uses a LangGraph supervisor to coordinate filings research, financial data, quantitative analysis, and risk comparison. Answers link to source passages; calculations retain their inputs and methods.

Development happens locally, with direct Codex testing for individual agents and [Kessel](https://github.com/waderylan/kessel) for full application runs. The deployment plan uses Nebius Token Factory and a second provider, currently NVIDIA NIM under consideration, with a streaming FastAPI frontend on Cloud Run.

Current stage: project specification and repository scaffold. Setup and deployment instructions will be added as the application takes shape.

- [Project spec and diagram](docs/planning/PROJECT_SPEC.md)
- [Assignment requirements](docs/assignment/Assignment_2_Description.md)
