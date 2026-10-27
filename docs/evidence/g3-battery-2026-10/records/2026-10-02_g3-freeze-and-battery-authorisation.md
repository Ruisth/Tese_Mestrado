# G3 candidate freeze and battery — Rui's authorisation (2026-10-02)

**Rui's words (2026-10-02, to the Senior Software Developer):** "Eu autorizo o parecer do PM a ser executado" ("I authorise the PM's opinion to be executed").

**What the opinion is.** The Project Manager's register entry "2026-10-01 22:50 WEST — freeze/battery packet favourable with operational conditions" (`ChatGPT/PROJECT_MANAGEMENT_INSTRUCTION_REGISTER.md`), relayed by Rui on 2026-10-01 with the PM's proposed wording:

> Aprovo Q1 e Q2 com as quatro condições do PM. Autorizo a preparação e S1 na próxima janela acompanhada; S2 na janela seguinte, desde que S1 termine sem uma condição de paragem. Não autorizo repetições, alterações ao candidato ou aceitação automática do G3.

**How it is read here** (the packet is `2026-10-01_g3-candidate-freeze-and-battery-packet.md`, revision 2, sha256 `d4b215dda0bdb760…`):

- **Q1, granted.** The candidate of the packet's §1 is frozen for the G3 qualifying battery: tools at `80e833f` (tree `dad725d`), the retained images, no change to code, configuration or helpers until the battery ends.
- **Q2, granted, for this battery only,** with the PM's four conditions (official purpose for the 12 qualifying rows; the current labelled environment capture as the harness input; the 3 h cutoff for starting a row on one host `/proc/uptime` baseline; the recorded `compose stop -t 130` before the unchanged close driver) and the recommended execution choices (130 s drain; S1 = T1–T5, S2 = T6–T9; the `-q1` ids; the prose-only steps run and recorded; a T7 with no visible effect is "not demonstrated" and not passed).
- **Order.** The host preparation (packet §7, no guest), then S1 in the next attended window, then S2 in the following attended window, provided S1 reaches its planned end without a halt condition.
- **Not authorised.** Repeats, any change to the candidate, automatic acceptance of G3. A halt cancels further progress under the packet until Rui directs otherwise.

**What stays open.** S1 starts only after the preparation is verified against the packet's §1 and its package has gone to Rui, and in a window Rui attends. G3 stays `Not decided` until the results are judged against the adopted criteria.
