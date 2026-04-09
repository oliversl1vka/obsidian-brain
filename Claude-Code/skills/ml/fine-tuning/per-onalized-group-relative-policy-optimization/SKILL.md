---
name: per-onalized-group-relative-policy-optimization
description: Implements a reinforcement learning algorithm for LLM fine-tuning that
  normalizes advantage estimates within distinct preference groups to better align
  models with heterogeneous human preferences. Use when fine-tuning models with diverse
  user feedback to preserve minority signals and improve convergence.
artifact_type: skill
domain_path: ml/fine-tuning
source_urls:
- https://machinelearning.apple.com/research/personalized-group
brain_entry: Entries/2026-04-09-personalized-group-relative-policy-optimization-for-heteroge
---

# Personalized Group Relative Policy Optimization (P-GRPO)

## When to Use
- Fine-tune LLMs with reinforcement learning on human preference data exhibiting heterogeneous user groups.
- Preserve minority user preference signals that standard group normalization suppresses.
- Improve convergence speed and alignment quality in multi-preference feedback environments.

## Overview
Personalized Group Relative Policy Optimization (P-GRPO) extends Group Relative Policy Optimization (GRPO) by normalizing advantage estimates within distinct preference groups instead of a global batch. This decouples advantage normalization from immediate batch statistics and preserves group-specific reward distributions.

Unlike GRPO, which assumes all samples are exchangeable and biases toward dominant preferences, P-GRPO:

- Normalizes advantages using preference-group-specific reward histories.
- Retains contrastive signals within minority groups.
- Facilitates faster convergence.
- Maintains alignment fidelity across heterogeneous preferences.

## Workflow
1. **Group Samples by Preference:** Partition training data into distinct user preference groups.
2. **Calculate Rewards per Group:** Maintain reward histories specific to each preference group.
3. **Normalize Advantages per Group:** Compute advantage estimates normalized within each group using the group-specific reward statistics.
4. **Policy Update:** Apply policy optimization using these normalized advantages to update the model.
5. **Iterate:** Repeat over batches while updating reward histories to progressively align model behavior.

## Guidelines
- Maintain accurate grouping labels to reflect true user preference clusters.
- Use sufficient history length per group to stabilize normalization.
- Monitor minority group reward signals to ensure they remain significant during training.
- Compare convergence and reward improvements baselined against standard GRPO.

## Benefits
- Prevents suppression of signals from less represented user groups.
- Enables personalized alignment across diverse human preferences.
- Achieves better reward maximization and model behavior fidelity.
- Scales well to large datasets with multiple heterogeneous preference groups.

## References
- [Personalized Group Relative Policy Optimization for Heterogeneous Preference Alignment](https://machinelearning.apple.com/research/personalized-group)
