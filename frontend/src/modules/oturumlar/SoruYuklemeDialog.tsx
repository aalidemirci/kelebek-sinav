// Soru PDF'i yükleme diyaloğu — iki yerde AYNI alanlarla sorulur: dersin soru
// dosyası (`SorularPaneli`) ve BEP kapsamındaki öğrencinin bireysel soru dosyası
// (`bep/BireyselSorularBolumu`). Gövde backend `QuestionUploadSerializer` ile
// birebir çok parçalı formdur: `file`, `score_mode`, isteğe bağlı `question_count`.
//
// Çağıran diyaloğu AÇIKKEN kurar (`{open && <SoruYuklemeDialog … />}`): her
// açılışta dosya seçimi sıfırdan başlar (kapatılan diyaloğun dosya alanı DOM'dan
// kalkar; seçim durumda kalsaydı boş görünen alanla "Yükle" açık kalırdı). Puan
// bölümü, yüklü dosyanınkiyle ön-dolar — "Değiştir"de yeniden seçtirmemek için.

import { useState } from "react";

import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import Select from "../../ui/Select";
import TextField from "../../ui/TextField";
import type { ScoreModeCode } from "./api";

interface SoruYuklemeDialogProps {
  title: string;
  /** Yüklü dosyanın puan bölümü (varsa) — alanlar bununla ön-dolar. */
  initialScoreMode?: ScoreModeCode;
  initialQuestionCount?: number | null;
  /** Yükleme sürüyor — düğme kapanır, etiketi "Yükleniyor…" olur. */
  pending: boolean;
  onClose: () => void;
  onSubmit: (form: FormData) => void;
}

export default function SoruYuklemeDialog({
  title,
  initialScoreMode = "SINGLE_BOX",
  initialQuestionCount = null,
  pending,
  onClose,
  onSubmit,
}: SoruYuklemeDialogProps) {
  const [file, setFile] = useState<File | null>(null);
  const [scoreMode, setScoreMode] = useState<ScoreModeCode>(initialScoreMode);
  const [questionCount, setQuestionCount] = useState(
    initialQuestionCount === null ? "" : String(initialQuestionCount),
  );

  const submit = () => {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("score_mode", scoreMode);
    if (scoreMode === "QUESTION_TABLE" && questionCount) {
      form.append("question_count", questionCount);
    }
    onSubmit(form);
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title={title}
      actions={
        <>
          <Button variant="text" onClick={onClose}>
            Vazgeç
          </Button>
          <Button onClick={submit} disabled={pending || !file}>
            {pending ? "Yükleniyor…" : "Yükle"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-label-large text-on-surface-variant">
          Soru PDF dosyası
          <input
            type="file"
            accept="application/pdf"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="min-h-9 rounded-shape-xs border border-outline bg-surface px-3 py-1.5 text-body-medium text-on-surface file:mr-3 file:rounded-shape-sm file:border-0 file:bg-secondary-container file:px-3 file:py-1 file:text-label-large file:text-on-secondary-container"
          />
        </label>
        <Select
          label="Puan bölümü"
          options={[
            { value: "SINGLE_BOX", label: "Tek puan kutusu" },
            { value: "QUESTION_TABLE", label: "Soru bazlı puan tablosu" },
          ]}
          value={scoreMode}
          onChange={(e) => setScoreMode(e.target.value as ScoreModeCode)}
        />
        {scoreMode === "QUESTION_TABLE" && (
          <TextField
            label="Soru sayısı"
            type="number"
            min={1}
            max={60}
            value={questionCount}
            onChange={(e) => setQuestionCount(e.target.value)}
            required
          />
        )}
      </div>
    </Dialog>
  );
}
