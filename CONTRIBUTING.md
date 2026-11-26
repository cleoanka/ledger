# Refuting a claim

> **Türkçe aşağıda.**

Every claim in this ledger can be refuted. Doing so is welcome: an accepted refutation changes the claim's status and puts your name on the list below.

## What counts

**A valid refutation** is either

- a reproducible run against the claim's **pinned commit**, under the claim's **own conditions**, whose
  number lands outside the claim's tolerance, or
- a **method error** that voids the claim, for example future data leaking into a backtest or test data
  mixed into training.

**Not a refutation**:

- a different result under different conditions (this may lead to the claim being marked `weakened`,
  but it does not count as a refutation),
- typos and wording,
- performance differences on hardware the claim does not name,
- statements about projects that are not in this ledger.

Security issues on www.cleoanka.com are outside this program. Report them privately as
[security.txt](https://www.cleoanka.com/.well-known/security.txt) says.

## How

1. Open an issue with the **Refutation** form. Include the exact commands from a clean checkout of the
   pinned commit, your environment, the number you measured and why it refutes the claim.
2. First response within **7 days**, decision within **30 days**.
3. The owner has the final say, and the reason for every decision is written publicly in the issue.
4. The first person to bring a refutation gets it; duplicates do not.

An accepted refutation changes the claim's status to `refuted` (or `weakened`) in a commit that links the
issue, and the refutation is listed in the claim's `refutations` field.

## Refuters

No one has refuted a claim yet. Be the first.

---

# Bir iddiayı çürütmek

Bu defterdeki her iddia çürütülebilir. Çürütmeye çalışmanız memnuniyetle karşılanır: kabul edilen bir çürütme iddianın durumunu değiştirir ve adınızı aşağıdaki listeye ekler.

## Ne sayılır

**Geçerli bir çürütme** şunlardan biridir:

- iddianın **sabitlenmiş commit'ine** karşı, iddianın **kendi koşullarında**, sayıyı iddianın toleransının
  dışına çıkaran yeniden üretilebilir bir çalıştırma;
- iddiayı geçersiz kılan bir **yöntem hatası**, örneğin bir geriye dönük testte gelecek verisinin sızması
  ya da test verisinin eğitime karışması.

**Çürütme sayılmaz**:

- farklı koşullarda farklı bir sonuç (iddianın `weakened`, yani "zayıfladı" olarak işaretlenmesine yol
  açabilir ama çürütme sayılmaz),
- yazım hataları ve üslup,
- iddianın belirtmediği donanımda performans farkları,
- bu defterde olmayan projeler hakkındaki ifadeler.

www.cleoanka.com'daki güvenlik açıkları bu programın dışındadır. Onları
[security.txt](https://www.cleoanka.com/.well-known/security.txt) dosyasında yazdığı gibi gizli olarak
bildirin.

## Nasıl

1. **Refutation** formuyla bir issue açın. Sabitlenmiş commit'in temiz bir kopyasından çalıştırdığınız tam
   komutları, ortamınızı, ölçtüğünüz sayıyı ve bunun iddiayı neden çürüttüğünü yazın.
2. İlk yanıt **7 gün**, karar **30 gün** içinde gelir.
3. Son söz sahibindedir; her kararın gerekçesi issue'da herkese açık olarak yazılır.
4. Bir çürütmeyi ilk getiren alır; aynısını sonradan getirenler almaz.

Kabul edilen bir çürütme, iddianın durumunu issue'ya bağlantı veren bir commit ile `refuted` ("çürütüldü")
ya da `weakened` ("zayıfladı") yapar ve çürütme iddianın `refutations` alanına eklenir.

## Çürütenler

Henüz kimse bir iddiayı çürütmedi. İlk siz olun.
