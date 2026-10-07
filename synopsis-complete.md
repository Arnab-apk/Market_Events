# Project synopsis — complete extracted text

Source: Project Synopsis Generative AI Stock Investment Platform.pdf (4 pages). Text is preserved as extracted; original spelling and reference claims are not corrected. The diagram transcription below supplements the embedded text.

## Page 1

```text
PROJECT SYNOPSIS REPORT
                     (Phase 1 – 5th Semester)of

                               the Final Year Project titled

      A HETEROGENOUS LLM-VLM-SLM
  APPROACH TO MULTI-AGENT EVENT
DETECTION AND CROSS-MARKET SIGNAL
FUSION FOR INDIAN FINANCIAL MARKETS

                         Submitted for partial
             fulfillment of the requirements for the degree of

      BACHELOR OF TECHNOLOGY
                                                      in

     COMPUTER SCIENCE & ENGINEERING

                                             by

                   Arnab Mandal — 16900124128
                    Asmit Biswas — 169001124120
              Biswaranjan Chakraborty — 169001124135
                   Akash Kundu — 16900124149

                      Under The Guidance of

                     Prof. Sumit Gupta

                             Assistant Professor

          Department Of Computer Science and Engineering,

                   Academy Of Technology





         ACADEMY OF TECHNOLOGY
                     G. T. Road (Adisaptagram), Aedconagar
                Hooghly – 712121, West Bengal, India
```

## Page 2

```text
PROJECT SYNOPSIS



1. Abstract
The proposed Generative AI-Based Intelligent Stock Investment Platform is a multi-agent framework for
analysing  financial market information across equities, derivatives and commodities. The system combines
news and macroevent understanding with technical, derivatives and commodity signals so that a detected
catalyst is evaluated against actual market behaviour before a recommendation is surfaced. A heterogeneous
model architecture is used, with Small Language Models (SLMs) for triage, Large Language Models (LLMs)
for entity resolution, sentiment, event detection and summarisation, Vision Language Models (VLMs) for chart
and candlestick analysis, and quantitative/rule-based modules for market confirmation. A fusion layer
aggregates the signals and produces a ranked, explainable output with confidence and provenance. The
proposed evaluation design includes backtesting,  ablation, walk-forward validation, Monte Carlo analysis and
live paper trading.

2. Overview
Financial markets generate a high volume of news, filings, macro reports and market-data signals.
The project addresses the challenge of turning these heterogeneous information sources into a structured
decision-support  pipeline. News provides the potential catalyst, while market data provides confirmation of
whether the instrument is  actually responding. The platform therefore follows a catalyst-to-confirmation
approach rather than relying on sentiment alone.
     ❖  Multi-agent orchestration for news, macro and market-data workflows.
     ❖ News analysis using entity resolution, sentiment, event detection and summarisation.
     ❖  Chart and candlestick interpretation through a vision-based analysis tier.
         Equity confirmation using RSI, volume profile and price-action/candlestick signals.
     ❖  Derivatives confirmation using Open Interest, Put-Call Ratio and Implied Volatility.
     ❖ Commodity confirmation using MCX price/volume signals against macro drivers.
     ❖ Weighted signal fusion with confidence and provenance for explainable recommendations.

3. Challenges
     ❖  High information volume across news, filings and macro reports.
     ❖ Missed catalysts such as capacity expansion, supply disruption, OPEC action and currency
        movements.
     ❖  Difficulty distinguishing actionable news from information already priced into the market.
     ❖  Different asset classes require different confirmation signals.
     ❖  Monolithic models may degrade when applied across heterogeneous signal families.
     ❖ Need for transparent, auditable and confidence-aware recommendations.

4. Motivation
The motivation is to build a modular and explainable market-analysis framework in which specialised agents
handle specialised tasks and their outputs are combined only after cross-signal verification. This design aims
to reduce noisy signals and improve the traceability of how a recommendation is formed.

5. Objectives
     ❖ Develop a multi-agent architecture for financial event and market analysis.
     ❖  Integrate news understanding with technical, derivatives and commodity confirmation.
     ❖ Match LLM, VLM, SLM and rule-based components to appropriate tasks.
     ❖ Implement a fusion mechanism for ranked and explainable recommendations.
     ❖  Attach confidence and provenance to agent outputs.
     ❖  Evaluate the framework through backtesting, ablation, walk-forward and robustness experiments.
```

## Page 3

```text
6. Prior Work (Literature Review)

                      Work                                    Approach                                   Identified Limitation

             Chen & Madisetti (2026)             Multi-agent event-driven market analysis        No cross-asset confirmation stage

                StockAgent (2025)              LLM agents in trading environments           Controlled simulation; no
                                                                                                        live-exchange validation

     LLM Event-Driven Forecasting (2026)         Structured financial event extraction            No technical/derivatives fusion

         Schumaker & Chen — AZFinText         Financial-news sentiment classification         Single-source sentiment; no market
                                                                                                                  confirmation

7. Proposed Methodology
     ❖  Orchestration & ingestion — workflow routing, shared state, news and macro retrieval
     ❖ Language tier — SLM triage; LLM entity resolution, sentiment, event detection and
        summarisation
     ❖  Vision tier — VLM-based candlestick and chart-pattern cross-verification
     ❖  Quantitative tier — equity technicals; derivatives OI/PCR/IV; commodities with MCX and
        macro signals  • Decision tier — weighted fusion for ranked, explainable recommendations
     ❖ Message-level provenance — task type, payload, output, confidence and source information

8. Technology & Evaluation Plan





     ❖ NLP & Sentiment: spaCy, Hugging Face Transformers, FinBERT
         sentence-transformers.
     ❖ Market Data & Backend: yfinance, Zerodha Kite Connect, FastAPI,
        PostgreSQL.
     ❖  Orchestration & Evaluation: LangGraph-style graph, backtesting.py,
          vectorBt.
     ❖  Storage & Monitoring: Redis, MongoDB, Prometheus.
     ❖  Evaluation: backtest, ablation, walk-forward, Monte Carlo and live paper trading.
```

## Page 4

```text
9. References
 [1] Chen, Q., & Madisetti, V. (2026). Event-driven market analysis via multi-agent systems. IEEE Transactions on Big Data, 12(4),
1449–1461.
 [2] IEEE FinEng. (2026). Multi-asset multi-agent RL for dynamic portfolio management. IEEE TNNLS, 37(3), 1120–1132.
 [3] Xiao, L., & Zhang, W. (2026). StockAgent: Simulating LLMs in trading environments. ACM TIST, 17(2), 101–118.
 [4] Schumaker, R. P., & Chen, H. (2009). Textual analysis via AZFinText system. ACM TOIS, 27(2), 12:1–12:19.
 [5] Wang, H., & Liu, K. (2026). LLM event-driven forecasting in financial services. Springer SOCA, 20(1), 45–58.
 [6] Zhang, Y., & Tan, C. (2025). Hierarchical deep RL for dynamic portfolio optimization. Complex Intelligence Systems, 11(2),
205–221.
 [7] De Silva, A., & Roberts, M. (2026). Fine-tuning in financial NLP action detection. Information Processing & Management, 63(8),
104910.
 [8] Gidófalvi, G., & Elkan, C. (2009). Quantitative stock prediction using financial news. Expert Systems with Applications, 36(3),
5432–5440.
 [9] Campbell, R., & Gallagher, P. (2026). Shapley domain explainability for financial language models. European Journal of Finance,
32(5), 412–430.





Signature of Students with Date                                               Signature of Guide with Date
```

## Page 3 — architecture diagram transcription

- **User Query:** e.g., Nifty outlook, Stock analysis.
- **Orchestration & Ingestion:** workflow routing, shared state, news & macro retrieval.
- Four inputs beneath orchestration:
  - **Market Data:** price feeds, OHLCV, OI, PCR, IV.
  - **News & Macro:** financial news, economic indicators.
  - **Charts / Images:** candlestick charts, pattern snapshots.
  - **User Context:** preferences, asset type, time horizon.
- Three analysis tiers beneath these inputs:
  - **Language Tier:** SLM triage; LLM entity resolution, sentiment, event detection and summarisation.
  - **Vision Tier:** VLM-based candlestick and chart-pattern cross-verification.
  - **Quantitative Tier:** equity technicals; derivatives OI/PCR/IV; commodities with MCX and macro signals.
- **Decision Tier:** weighted fusion for ranked, explainable recommendations.
- Dashed connection to **Message-level Provenance:** task type, payload, output, confidence, source information.
- **Final Recommendation:** ranked signals with explanation.

Flow: User Query → Orchestration & Ingestion → input branches → analysis tiers → Decision Tier → Final Recommendation. Provenance is connected to the decision tier.

## Other visual content

Page 1 contains the Academy of Technology (AOT) logo. Page 3 contains the literature-review table, whose text is included above, and the architecture diagram transcribed here. Page 4 has student and guide signature labels, with no signatures visible in the extracted text.
