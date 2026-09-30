# Fraud Rule Engine

A pure-Python, local-first fraud/risk rule engine. It deliberately contains no
web framework, database driver, authentication, notification, or cloud SDK.

## Architecture

```text
application / tests / example
             |
             v
        RuleEngine  <--- injected Rule instances
             |
             +---- builds RuleContext from TransactionRepository
             |                 |
             |                 v
             |        InMemoryTransactionRepository (today)
             |        MongoTransactionRepository    (later)
             |
             +---- evaluates independent Rule implementations
                      discovered from fraud_engine.rules
```

`RuleEngine` depends on the abstract `Rule` and `TransactionRepository`
contracts. The composition helper in `fraud_engine.discovery` selects the
in-memory implementation and turns registered classes into injected instances.
Changing storage later therefore does not change the engine or any rule.

## Design choices

- **ABC contracts:** `Rule` specifies stable IDs, display names, and an
  `evaluate(transaction, context)` method. `TransactionRepository` specifies
  only operations needed to build context. This makes replacements explicit
  and type-friendly.
- **Constructor dependency injection:** `RuleEngine(repository, rules, ...)`
  receives both collaborators. It neither imports concrete rules nor creates a
  concrete repository.
- **Rule context:** Rules receive a `RuleContext` with prior transactions, the
  previous transaction, and a precomputed historical average. Rules never
  query the repository.
- **In-memory storage:** `InMemoryTransactionRepository` stores normal Python
  objects, sorts per-user history by time, and returns immutable tuples. It is
  intended for local development and tests.
- **Transaction timing:** The engine builds context before saving the current
  transaction. That prevents the item being assessed from altering its own
  amount baseline or history. `VelocityRule` deliberately counts the current
  transaction plus prior items in its window; its default threshold is five.

## Built-in rules

| Rule | Default score | Trigger |
| --- | ---: | --- |
| Transaction velocity | 30 | At least 5 transactions, including current, in 10 minutes |
| Unusual transaction amount | 25 | Amount strictly exceeds 3x the prior historical average |
| Impossible geographical location | 45 | Required travel speed strictly exceeds 900 km/h |

The engine sums only triggered scores, caps the score at 100, and marks an
assessment high risk at its configurable default threshold of 70.

## Registration and automatic discovery

`@register_rule` maps a stable rule ID to a rule class in `RULE_REGISTRY`.
`discover_rules()` uses `pkgutil` and `importlib` to import every module in
`fraud_engine.rules`; importing a module runs its decorator. The engine itself
has no registry or concrete-rule references.

To add a rule, add a module such as
`fraud_engine/rules/suspicious_merchant.py`:

```python
from fraud_engine.interfaces import Rule, RuleContext
from fraud_engine.models import RuleResult, Transaction
from fraud_engine.registry import register_rule


@register_rule
class SuspiciousMerchantRule(Rule):
    RULE_ID = "suspicious_merchant"

    @property
    def rule_id(self) -> str:
        return self.RULE_ID

    @property
    def name(self) -> str:
        return "Suspicious merchant"

    def evaluate(self, transaction: Transaction, context: RuleContext) -> RuleResult:
        flagged = transaction.merchant == "Known risky merchant"
        return RuleResult(self.rule_id, self.name, flagged, 20 if flagged else 0, "...")
```

Then create an engine through the composition root; no `RuleEngine` edit is
required:

```python
from fraud_engine.discovery import build_discovered_engine

engine = build_discovered_engine(repository)
```

Pass per-rule construction settings without coupling them to the engine:

```python
engine = build_discovered_engine(
    repository,
    rule_configurations={"transaction_velocity": {"max_transactions": 3}},
    high_risk_threshold=60,
)
```

## Run locally

Python 3.11+ is required. The engine itself has no third-party dependencies;
the test suite uses pytest.

```bash
python -m pytest
python example.py
```

The tests cover each rule's edge cases, registry registration, module
discovery, score capping, configurable thresholds, and a test-only decorated
rule that becomes available without changing `RuleEngine`.
