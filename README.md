# Local Audio Transcriber

Локальное приложение для записи аудио с микрофона и транскрибации аудиофайлов через `faster-whisper`.

## Возможности

- выбор устройства записи;
- запись системного звука Windows через WASAPI loopback;
- режим микрофон + системный звук в два отдельных WAV;
- индикация уровня микрофона до и во время записи;
- индикация уровня системного звука;
- потоковая запись микрофона в WAV;
- диагностика записи: duration, sample rate, channels, RMS, Peak, размер файла, признак тишины;
- загрузка файлов `.wav`, `.mp3`, `.m4a`;
- транскрибация через модель Whisper `small`;
- автоматическая попытка использовать CUDA и fallback на CPU;
- benchmark после транскрибации: длительность аудио, время обработки, скорость realtime;
- сохранение `.txt` и диагностических `.json`.

## Создание виртуального окружения

```bat
cd /d C:\Python\LocalAudioTranscriber
python -m venv .venv
```

## Установка зависимостей

```bat
cd /d C:\Python\LocalAudioTranscriber
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Все библиотеки устанавливаются только в:

```text
C:\Python\LocalAudioTranscriber\.venv
```

## Запуск

```bat
cd /d C:\Python\LocalAudioTranscriber
run.bat
```

Интерфейс:

```text
http://127.0.0.1:8000
```

## Как выбрать микрофон

В блоке записи выберите режим `Микрофон`, затем поле `Микрофон`. В списке отображаются имя устройства, количество входных каналов, sample rate и признак устройства по умолчанию.

Если список неактуален, нажмите `Обновить список устройств`.

Если устройство не выбрано явно, приложение использует default input device Windows и показывает его имя в интерфейсе.

## Микрофон и системный звук

`Микрофон` записывает звук с выбранного input device. Это подходит для диктовки, личных заметок и живого голоса рядом с ноутбуком.

`Системный звук` записывает output-поток Windows через WASAPI loopback: браузер, YouTube, онлайн-встречу, медиаплеер или звук выбранных наушников/динамиков. Для YouTube и онлайн-встреч это обычно лучше, чем схема `динамики -> воздух -> микрофон`, потому что в WAV попадает чистый цифровой поток без шума комнаты, эха и качества микрофона.

`Микрофон + системный звук` пишет два отдельных файла:

```text
mic_YYYYMMDD_HHMMSS.wav
system_YYYYMMDD_HHMMSS.wav
```

Файлы не смешиваются намеренно: микрофон может добавить шум, эхо и речь из комнаты, а чистый системный звук лучше оставить отдельной дорожкой.

## Как выбрать системное output-устройство

В режиме `Системный звук` выберите `Устройство вывода`. Обычно это то же устройство, через которое сейчас слышен звук Windows:

- Headphones / Realtek Audio;
- Speakers / Realtek Audio;
- Bluetooth headphones;
- HDMI / NVIDIA / Display Audio.

Если вы слушаете через наушники, выбирайте наушники. Если звук идет на монитор/TV по HDMI, выбирайте HDMI/Display Audio.

Список output devices берется через WASAPI loopback. Endpoint:

```text
GET /api/audio/output-devices
```

## Как проверить системный звук

Включите YouTube, браузер или онлайн-встречу и посмотрите на `Уровень системного звука`. Если звук реально идет через выбранное output-устройство, шкала должна двигаться, а RMS/Peak должны быть выше нуля.

Если шкала не двигается:

- выберите другое output-устройство;
- проверьте, куда Windows выводит звук;
- убедитесь, что звук не поставлен на паузу и не заглушен;
- проверьте громкость приложения в Windows Volume Mixer.

## Как проверить уровень сигнала

В блоке записи отображаются:

```text
Уровень микрофона
RMS
Peak
```

Индикатор обновляется несколько раз в секунду. До начала важной записи скажите несколько слов и убедитесь, что Peak/RMS растут.

## Что делать, если записывается тишина

После остановки записи приложение считает RMS и Peak всего WAV. Если оба значения ниже порогов, появится предупреждение:

```text
Запись похожа на тишину. Проверьте выбранный микрофон или уровень входного сигнала.
```

Файл не удаляется автоматически. Проверьте:

- выбран ли правильный микрофон;
- не выбран ли Stereo Mix вместо микрофона;
- разрешен ли доступ к микрофону в Windows;
- виден ли сигнал на индикаторе перед записью;
- не отключен ли микрофон аппаратной кнопкой или в микшере.

Для системного звука предупреждение выглядит так:

```text
Системная запись похожа на тишину. Проверьте, что звук воспроизводится в Windows и выбрано правильное устройство вывода.
```

В этом случае чаще всего выбран не тот output device или звук фактически идет через другое устройство.

Пороги настраиваются в `app\config.py`:

```python
SILENCE_RMS_THRESHOLD = 0.0015
SILENCE_PEAK_THRESHOLD = 0.01
```

## Где лежат записи и диагностика

Записи WAV:

```text
C:\Python\LocalAudioTranscriber\data\recordings
```

Рядом с каждой записью сохраняется JSON:

```text
recording_YYYYMMDD_HHMMSS.json
system_YYYYMMDD_HHMMSS.json
mic_YYYYMMDD_HHMMSS.json
```

В нем есть путь к WAV, `source_type`, устройство записи или output-устройство, sample rate, channels, duration, file size, RMS, Peak, `is_silence` и warnings.

Загруженные аудиофайлы:

```text
C:\Python\LocalAudioTranscriber\data\uploads
```

Транскрипты:

```text
C:\Python\LocalAudioTranscriber\data\transcripts
```

Рядом с каждым transcript `.txt` сохраняется benchmark JSON:

```text
transcript_YYYYMMDD_HHMMSS.json
```

Логи:

```text
C:\Python\LocalAudioTranscriber\data\logs\app.log
```

Кэш моделей и временные файлы:

```text
C:\Python\LocalAudioTranscriber\models
C:\Python\LocalAudioTranscriber\tmp
```

## Настройки Whisper

По умолчанию:

```python
WHISPER_MODEL = "small"
WHISPER_LANGUAGE = "ru"
WHISPER_DEVICE = "auto"
WHISPER_COMPUTE_TYPE = "auto"
WHISPER_BEAM_SIZE = 1
WHISPER_VAD_FILTER = True
WHISPER_CONDITION_ON_PREVIOUS_TEXT = False
```

Модель `small` не понижается автоматически. Если CUDA не работает, приложение переключается на CPU с той же моделью.

## Как включить GPU

По умолчанию GPU включается автоматически:

```bat
set WHISPER_DEVICE=auto
set WHISPER_COMPUTE_TYPE=auto
run.bat
```

Приложение пробует CUDA compute types:

```text
float16
int8_float16
int8
```

Если CUDA не загрузилась, приложение логирует ошибку и переходит на CPU `int8`.

Для принудительной проверки CUDA:

```bat
set WHISPER_DEVICE=cuda
set WHISPER_COMPUTE_TYPE=auto
run.bat
```

## Ошибка cublas64_12.dll

Ошибка вида:

```text
Library cublas64_12.dll is not found or cannot be loaded
```

означает, что `ctranslate2` видит CUDA, но не находит cuBLAS runtime. Для этого проекта cuBLAS/cuDNN ставятся локально в `.venv` через:

```text
nvidia-cublas-cu12
nvidia-cudnn-cu12
nvidia-cuda-nvrtc-cu12
```

Системный CUDA Toolkit не требуется, если эти wheels установились корректно.

## Как проверить скорость транскрибации

После каждой транскрибации интерфейс показывает:

```text
Длительность аудио
Время обработки
Скорость
Устройство
Compute type
Модель
```

Пример:

```text
Длительность аудио: 300 сек
Время обработки: 75 сек
Скорость: 4.0x realtime
Устройство: cuda
Модель: small
```

Те же данные сохраняются в `data\transcripts\transcript_YYYYMMDD_HHMMSS.json`.

Если транскрибируется записанный системный или микрофонный файл из режима `Микрофон + системный звук`, имена будут отдельными:

```text
transcript_system_YYYYMMDD_HHMMSS.txt
transcript_mic_YYYYMMDD_HHMMSS.txt
```

## ffmpeg

Для `.mp3` и `.m4a` нужен `ffmpeg` в `PATH`. Приложение проверяет его наличие и показывает ошибку, если `ffmpeg` не найден.

## Ограничения

Не реализованы:

- запись и транскрибация видео;
- LLM-резюме;
- авторизация;
- мобильный клиент;
- Docker;
- база данных;
- diarization и разделение говорящих;
- облачный режим и серверное развертывание.
