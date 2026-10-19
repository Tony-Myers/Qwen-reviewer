#!/bin/bash
# Model paths and alias resolution, shared by the launchers.
#
# This existed twice: start_server.sh had a case statement and
# scripts/qwen_service.sh had none at all, so "--model flash" set the model to
# the literal string "flash", which does not end in .gguf and therefore
# selected the MLX backend. Adding a model meant editing up to four places --
# MODEL_ALIASES in app/review_pipeline.py, MODEL_CHOICES in app/server.py, and
# both launchers -- and the one that was missed each time failed differently.
#
# MODEL_ALIASES in app/review_pipeline.py remains canonical; this cannot read
# it, because aliases are resolved while parsing arguments, before the virtual
# environment is active. tests/test_model_aliases.py fails if the two disagree.
#
# Sourced, not executed. Defines the model variables and resolve_model().

HF_HUB="${HF_HUB_CACHE:-$HOME/.cache/huggingface/hub}"

QWEN38_27B_GGUF="$HF_HUB/models--unsloth--Qwen3.8-27B-GGUF/snapshots/4ca720788d1e01f1bff70c033e0d0028fd02e502/Qwen3.8-27B-UD-Q4_K_XL.gguf"
# 28 shards; llama-server is given the first and finds the rest. The GGUF
# declares the architecture qwen4exp -- not qwen3next, whatever the file name
# suggests -- and the Homebrew build does not know it: the load fails with
# "unknown model architecture: 'qwen4exp'". Set LLAMA_SERVER_BIN to a build
# that has it, and see local.env.example for how to make that setting survive
# a restart started from the browser.
QWEN38_FLASH_NEXT_GGUF="$HF_HUB/models--AtomicChat--Qwen3.8-Flash-Next-GGUF/snapshots/142262902a46f7daed19c79d0771534c8106ad59/Qwen3.8-Flash-Next-AD-3.84bpw-IQ4_XS-M64/Qwen3.8-Flash-Next-AD-3.84bpw-IQ4_XS-M64-00001-of-00028.gguf"

QWEN35_4BIT="mlx-community/Qwen3.6-35B-A3B-4bit"
QWEN27_6BIT="mlx-community/Qwen3.6-27B-6bit"
QWEN27_4BIT="mlx-community/Qwen3.6-27B-4bit"
QWEN27_8BIT="mlx-community/Qwen3.6-27B-8bit"
GEMMA4_26B_A4B_IT_4BIT="mlx-community/gemma-4-26b-a4b-it-4bit"
GEMMA4_31B_IT_4BIT="mlx-community/gemma-4-31b-it-4bit"

resolve_model() {
  case "$1" in
    qwen38|27b-gguf|gguf|qwen38-27b)
      echo "$QWEN38_27B_GGUF"
      ;;
    flash|flash-next|qwen38-flash)
      echo "$QWEN38_FLASH_NEXT_GGUF"
      ;;
    35b|35b-4bit|qwen35)
      echo "$QWEN35_4BIT"
      ;;
    27b|27b-6bit|qwen27)
      echo "$QWEN27_6BIT"
      ;;
    27b-4bit)
      echo "$QWEN27_4BIT"
      ;;
    27b-8bit)
      echo "$QWEN27_8BIT"
      ;;
    gemma4|gemma4-26b|gemma4-26b-it)
      echo "$GEMMA4_26B_A4B_IT_4BIT"
      ;;
    gemma4-31b|gemma4-31b-it)
      echo "$GEMMA4_31B_IT_4BIT"
      ;;
    *)
      if [[ "$1" == */* || "$1" == .* || "$1" == ~* ]]; then
        echo "$1"
      else
        echo "Unknown model alias: $1" >&2
        echo "Aliases are listed in scripts/model_aliases.sh and in" >&2
        echo "MODEL_ALIASES in app/review_pipeline.py. Both need the entry." >&2
        return 1
      fi
      ;;
  esac
}

# Extra llama-server flags a particular model needs, so that they travel with
# the model when it is chosen in the browser -- local.env cannot make a setting
# conditional on which model was picked. Empty for everything else.
#
# Flash-Next: --lazy-mode auto is in the invocation that is known to load this
# model on this machine. If it turns out to be unnecessary, this is one line to
# remove; LLAMA_SERVER_EXTRA_ARGS in local.env adds flags for every model.
model_extra_args() {
  case "$(basename "$1")" in
    Qwen3.8-Flash-Next-*)
      echo "--lazy-mode auto"
      ;;
    *)
      echo ""
      ;;
  esac
}
