# Meshtastic MQTT Sniffer / Meshtastic MQTT Dinleyici

EN:
> A command-line application that subscribes to Meshtastic MQTT traffic,
> displays decoded packets, and stores packet metadata in SQLite.

TR:
> Bir komut satırı uygulamasıdır, Meshtastic MQTT trafiğini dinler,
> çözümlenmiş paketleri görüntüler ve paket meta verilerini SQLite'da saklar.


## Setup / Kurulum

EN:
> I suggest using [uv](https://docs.astral.sh/uv/) to manage dependencies.

TR:
> [uv](https://docs.astral.sh/uv/) kullanarak kurulum ve gereksinimleri ayarlayabilirsiniz.


```sh
uv run sync
```
EN:
> Not `uv sync`

TR:
> `uv sync` değildir.

-----

EN:
> Copy `.env.example` to `.env` and fill it with your MQTT settings and credentials for persistent MQTT settings.

TR:
> `.env.example` dosyasını `.env` dosyasına kopyalayarak ve MQTT ayarlarını ve kullanıcı bilgilerini girerek kaydedin.


## Run / Çalıştırma

```sh
uv run meshtastic-mqtt-sniffer
```
EN:
> Run `uv run meshtastic-mqtt-sniffer --help` for connection overrides and other options.

TR:
> Kullanılabilir seçenekleri görmek için `uv run meshtastic-mqtt-sniffer --help` komutunu kullanabilirsiniz.


## FAQ / SSS

### ImportError with error message about protobuf / Protobuf ile ilgili ImportError
EN:
> Run `uv run sync` to install dependencies.

TR:
> `uv run sync` komutunu çalıştırarak gereksinimleri yükleyin.

### I only see errors on the terminal / Terminalde sadece hata mesajları görüyorum
EN:
> Use `--log-level` to set the log level to `INFO`.

TR:
> `--log-level` seçeneğini `INFO` olarak ayarlayarak günlük mesajlarını görebilirsiniz.
```sh
uv run meshtastic-mqtt-sniffer --log-level INFO
```

# Browse The Database / Veritabanını İncele

EN:
> You can use any SQLite browser to view the database.
> But I recommend using [Datasette](https://github.com/simonw/datasette) to browse the database as is is very easy to use.

TR:
> Veritabanını görüntülemek için herhangi bir SQLite görüntüleme aracı kullanabilirsiniz.
> Ama [Datasette](https://github.com/simonw/datasette) kullanmanızı tavsiye ederim çünkü çok kolay kullanılır.

```sh
uvx datasette packets.db
```
http://127.0.0.1:8001/packets/packets

EN:
> Then you can click on the gear icon next to column names and and select "Facet by this" to be able to see
> counts of that column's values and filter by them. (I recommend faceting by `sender` and `port_name`)

TR:
> Sütun adının yanındaki dişli sembolüne tıklayıp "Facet by this" seçeneğini seçerek sütundaki değerlerin sayısını
> görebilir ve o değerlere göre filtreleme yapabilirsiniz. (`sender` ve `port_name` sütunlarını yapmanızı öneririm)

> [!WARNING]
> AI has been used to assist with the development of this project. / Bu projenin geliştirilmesinde yapay zekadan yararlanılmıştır.
