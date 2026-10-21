# colab_ner

Готовая папка для обучения NER-модели в Google Colab — всё в одном месте,
без лишних файлов проекта.

## Содержимое

- `ner_training_colab.ipynb` — блокнот обучения (ruBERT-base, weak-разметка → BIO).
- `data/train.jsonl`, `data/val.jsonl` — weak-датасет (в git не хранится,
  см. `.gitignore`; копируется из `data/ner/`).

## Запуск

1. Загрузи всю папку `colab_ner` в Colab (или один zip с ней).
2. Открой `ner_training_colab.ipynb`.
3. `Среда выполнения → Сменить тип среды выполнения → T4 GPU`.
4. `Ctrl+F9` (запустить всё). Блокнот сам найдёт файлы данных рядом с собой;
   если не найдёт — покажет диалог загрузки `train.jsonl`/`val.jsonl`.

## Результат

По окончании скачается `ner_model.zip` (или скопируется в Google Drive, если он
смонтирован). Распакуй в `models/ner` проекта — модель подхватится
`TransformersSpanPredictor`.
