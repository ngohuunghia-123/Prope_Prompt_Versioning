import { useCallback, useEffect, useRef, useState } from 'react';

interface RecognitionAlternative {
  transcript: string;
}

interface RecognitionResult {
  readonly length: number;
  readonly isFinal: boolean;
  readonly [index: number]: RecognitionAlternative;
}

interface RecognitionEvent {
  readonly resultIndex: number;
  readonly results: { readonly length: number; readonly [index: number]: RecognitionResult };
}

interface RecognitionInstance {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: RecognitionEvent) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
}

type RecognitionConstructor = new () => RecognitionInstance;

function recognitionConstructor(): RecognitionConstructor | undefined {
  const speechWindow = window as typeof window & {
    SpeechRecognition?: RecognitionConstructor;
    webkitSpeechRecognition?: RecognitionConstructor;
  };
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
}

export function useVoiceInput(value: string, onChange: (value: string) => void, language: string) {
  const instance = useRef<RecognitionInstance | null>(null);
  const base = useRef('');
  const [listening, setListening] = useState(false);
  const supported = typeof window !== 'undefined' && recognitionConstructor() !== undefined;

  useEffect(() => () => instance.current?.stop(), []);

  const toggle = useCallback(() => {
    if (listening) {
      instance.current?.stop();
      setListening(false);
      return;
    }
    const Recognition = recognitionConstructor();
    if (!Recognition) return;
    const recognition = new Recognition();
    recognition.lang = language.startsWith('vi') ? 'vi-VN' : 'en-US';
    recognition.continuous = false;
    recognition.interimResults = true;
    base.current = value.trim();
    recognition.onresult = (event) => {
      let transcript = '';
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        transcript += event.results[index]?.[0]?.transcript ?? '';
      }
      onChange(`${base.current}${base.current && transcript ? ' ' : ''}${transcript}`.trim());
    };
    recognition.onend = () => setListening(false);
    recognition.onerror = () => setListening(false);
    instance.current = recognition;
    recognition.start();
    setListening(true);
  }, [language, listening, onChange, value]);

  return { listening, supported, toggle };
}
