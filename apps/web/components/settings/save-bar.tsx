"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Loader2, RotateCcw, Save } from "lucide-react";

export function SaveBar({
  dirty,
  saving,
  canManage,
  validationError,
  notice,
  error,
  isConflict,
  onSave,
  onReset,
}: {
  dirty: boolean;
  saving: boolean;
  canManage: boolean;
  validationError: string | null;
  notice: string | null;
  error: string | null;
  isConflict: boolean;
  onSave: () => void;
  onReset: () => void;
}) {
  const reduceMotion = useReducedMotion();

  if (!canManage) return null;

  return (
    <div className="saveBar">
      <div className="saveBarStatus">
        {dirty ? <span className="saveBarDirty"><span className="saveBarDot" aria-hidden="true" />Unsaved changes</span> : <span className="saveBarClean">Up to date</span>}
      </div>
      <div className="saveBarActions">
        <button className="smallButton" type="button" disabled={!dirty || saving} onClick={onReset}>
          <RotateCcw size={14} aria-hidden="true" />
          Reset
        </button>
        <button className="actionButton" type="submit" disabled={!dirty || Boolean(validationError) || saving} onClick={onSave}>
          {saving ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : <Save size={15} aria-hidden="true" />}
          {saving ? "Saving" : "Save changes"}
        </button>
      </div>

      <AnimatePresence>
        {validationError ? (
          <motion.p
            className="formError saveBarMessage"
            role="alert"
            initial={reduceMotion ? false : { opacity: 0, height: 0 }}
            animate={reduceMotion ? undefined : { opacity: 1, height: "auto" }}
            exit={reduceMotion ? undefined : { opacity: 0, height: 0 }}
          >
            <AlertTriangle size={14} aria-hidden="true" />
            {validationError}
          </motion.p>
        ) : null}

        {!validationError && error ? (
          <motion.p
            className={isConflict ? "saveBarMessage saveBarConflict" : "formError saveBarMessage"}
            role="alert"
            initial={reduceMotion ? false : { opacity: 0, height: 0 }}
            animate={reduceMotion ? undefined : { opacity: 1, height: "auto" }}
            exit={reduceMotion ? undefined : { opacity: 0, height: 0 }}
          >
            <AlertTriangle size={14} aria-hidden="true" />
            {error}
          </motion.p>
        ) : null}

        {!validationError && !error && notice ? (
          <motion.p
            className="saveBarMessage saveBarSuccess"
            role="status"
            initial={reduceMotion ? false : { opacity: 0, height: 0 }}
            animate={reduceMotion ? undefined : { opacity: 1, height: "auto" }}
            exit={reduceMotion ? undefined : { opacity: 0, height: 0 }}
          >
            <CheckCircle2 size={14} aria-hidden="true" />
            {notice}
          </motion.p>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
