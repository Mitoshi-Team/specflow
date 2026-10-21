"""Обучение NER-модели (token classification) на weak-датасете.

Запуск::

    python scripts/train_ner.py \
        --train data/ner/train.jsonl \
        --val data/ner/val.jsonl \
        --out models/ner

Скрипт конвертирует weak-разметку в BIO (``attribute_extractor.ner_dataset``),
дообучает базовую модель (ruBERT-base) и сохраняет модель, токенизатор,
``labels.json`` и ``metrics.json``. Тяжёлые зависимости импортируются лениво,
поэтому модуль импортируем без установленных torch/transformers.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from attribute_extractor.constants import (  # noqa: E402
    DEFAULT_NER_BASE_MODEL,
    NER_BIO_OUTSIDE,
    NER_BIO_PREFIX_BEGIN,
    NER_BIO_PREFIX_INSIDE,
    NER_LABELS_FILENAME,
    NER_TRAIN_BATCH_SIZE,
    NER_TRAIN_EPOCHS,
    NER_TRAIN_LEARNING_RATE,
    NER_TRAIN_MAX_LENGTH,
    NER_TRAIN_METRICS_FILENAME,
    NER_TRAIN_SEED,
)
from attribute_extractor.ner_dataset import (  # noqa: E402
    LABEL2ID,
    LABELS,
    load_weak_records,  # noqa: E402
    records_to_examples,
)


def entity_spans(labels: Sequence[str]) -> set[tuple[str, int, int]]:
    """BIO-метки → множество сущностей ``(класс, начало, конец)`` по токенам."""
    entities: set[tuple[str, int, int]] = set()
    start: int | None = None
    entity: str | None = None
    for index, label in enumerate(labels):
        if label == NER_BIO_OUTSIDE:
            if entity is not None and start is not None:
                entities.add((entity, start, index))
            start, entity = None, None
            continue
        if label.startswith(NER_BIO_PREFIX_BEGIN):
            if entity is not None and start is not None:
                entities.add((entity, start, index))
            start = index
            entity = label[len(NER_BIO_PREFIX_BEGIN) :]
        elif label.startswith(NER_BIO_PREFIX_INSIDE):
            current = label[len(NER_BIO_PREFIX_INSIDE) :]
            if entity != current:
                if entity is not None and start is not None:
                    entities.add((entity, start, index))
                start = index
                entity = current
    if entity is not None and start is not None:
        entities.add((entity, start, len(labels)))
    return entities


def micro_scores(
    true_entities: Sequence[set[tuple[str, int, int]]],
    pred_entities: Sequence[set[tuple[str, int, int]]],
) -> dict[str, float]:
    """Entity-level micro precision/recall/F1 (без внешних зависимостей)."""
    tp = fp = fn = 0
    for true, pred in zip(true_entities, pred_entities, strict=True):
        tp += len(true & pred)
        fp += len(pred - true)
        fn += len(true - pred)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": float(tp),
        "fp": float(fp),
        "fn": float(fn),
    }


def build_dataset(examples, tokenizer, max_length: int):
    """Оборачивает BIO-примеры в torch Dataset с выравниванием по word_ids."""
    import torch

    class _Dataset(torch.utils.data.Dataset):
        def __len__(self) -> int:
            return len(examples)

        def __getitem__(self, index: int):
            example = examples[index]
            encoded = tokenizer(
                example.words,
                is_split_into_words=True,
                truncation=True,
                max_length=max_length,
            )
            word_ids = encoded.word_ids()
            aligned: list[int] = []
            previous: int | None = None
            for word_id in word_ids:
                if word_id is None:
                    aligned.append(-100)
                elif word_id != previous:
                    aligned.append(LABEL2ID[example.labels[word_id]])
                else:
                    aligned.append(-100)
                previous = word_id
            encoded["labels"] = aligned
            return encoded

    return _Dataset()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Обучение NER на weak-датасете")
    parser.add_argument("--train", required=True, help="JSONL train")
    parser.add_argument("--val", required=True, help="JSONL validation")
    parser.add_argument("--out", required=True, help="Каталог для модели")
    parser.add_argument("--model", default=DEFAULT_NER_BASE_MODEL)
    parser.add_argument("--epochs", type=int, default=NER_TRAIN_EPOCHS)
    parser.add_argument("--batch-size", type=int, default=NER_TRAIN_BATCH_SIZE)
    parser.add_argument("--lr", type=float, default=NER_TRAIN_LEARNING_RATE)
    parser.add_argument("--max-length", type=int, default=NER_TRAIN_MAX_LENGTH)
    parser.add_argument("--seed", type=int, default=NER_TRAIN_SEED)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    from transformers import (
        AutoModelForTokenClassification,
        AutoTokenizer,
        DataCollatorForTokenClassification,
        Trainer,
        TrainingArguments,
    )

    train_examples = records_to_examples(load_weak_records(args.train))
    val_examples = records_to_examples(load_weak_records(args.val))
    print(f"train: {len(train_examples)}, val: {len(val_examples)}")

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForTokenClassification.from_pretrained(
        args.model,
        num_labels=len(LABELS),
        id2label=dict(enumerate(LABELS)),
        label2id=LABEL2ID,
        ignore_mismatched_sizes=True,
    )

    def compute_metrics(eval_prediction) -> dict[str, float]:
        logits, labels = eval_prediction
        predictions = logits.argmax(axis=-1)
        true_sets = []
        pred_sets = []
        for predicted_row, label_row in zip(predictions, labels, strict=True):
            true_labels = [
                LABELS[int(value)] if int(value) >= 0 else NER_BIO_OUTSIDE for value in label_row
            ]
            pred_labels = [LABELS[int(value)] for value in predicted_row]
            true_sets.append(entity_spans(true_labels))
            pred_sets.append(entity_spans(pred_labels))
        return micro_scores(true_sets, pred_sets)

    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        learning_rate=args.lr,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        eval_strategy="epoch",
        save_strategy="no",
        logging_steps=50,
        seed=args.seed,
        report_to="none",
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=build_dataset(train_examples, tokenizer, args.max_length),
        eval_dataset=build_dataset(val_examples, tokenizer, args.max_length),
        data_collator=DataCollatorForTokenClassification(tokenizer),
        compute_metrics=compute_metrics,
    )
    trainer.train()
    metrics = trainer.evaluate()
    print(f"metrics: {metrics}")

    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    (output_dir / NER_LABELS_FILENAME).write_text(
        json.dumps(LABELS, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / NER_TRAIN_METRICS_FILENAME).write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"model saved to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
