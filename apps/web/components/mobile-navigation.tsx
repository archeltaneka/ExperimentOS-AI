"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Menu, X } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";

import { Navigation } from "@/components/navigation";
import { Button } from "@/components/ui/button";

export function MobileNavigation() {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const reduceMotion = useReducedMotion();
  const close = () => { triggerRef.current?.focus(); setOpen(false); };
  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const handler = (event: KeyboardEvent) => { if (event.key === "Escape") close(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open]);
  const trapFocus = (event: ReactKeyboardEvent<HTMLElement>) => {
    if (event.key !== "Tab") return;
    const focusable = dialogRef.current?.querySelectorAll<HTMLElement>("a[href], button:not([disabled]), [tabindex]:not([tabindex='-1'])");
    if (!focusable?.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };
  return <><Button ref={triggerRef} aria-controls="mobile-navigation" aria-expanded={open} aria-haspopup="dialog" aria-label="Open navigation" className="lg:hidden" onClick={() => setOpen(true)} variant="outline"><Menu aria-hidden="true" /></Button><AnimatePresence>{open && <><motion.button aria-label="Close navigation" className="fixed inset-0 z-40 bg-background/75 backdrop-blur-sm lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: reduceMotion ? 0 : 0.16 }} onClick={close} /><motion.aside aria-label="Navigation" aria-modal="true" className="fixed inset-y-0 left-0 z-50 w-72 max-w-[calc(100vw-2rem)] border-r bg-background p-4 shadow-2xl lg:hidden" id="mobile-navigation" initial={{ x: "-100%" }} animate={{ x: 0 }} exit={{ x: "-100%" }} onKeyDown={trapFocus} ref={dialogRef} transition={{ duration: reduceMotion ? 0 : 0.18 }} role="dialog"><div className="mb-7 flex items-center justify-between"><span className="font-semibold">ExperimentOS AI</span><Button aria-label="Close navigation" onClick={close} ref={closeRef} variant="outline"><X aria-hidden="true" /></Button></div><Navigation onNavigate={close} /></motion.aside></>}</AnimatePresence></>;
}
