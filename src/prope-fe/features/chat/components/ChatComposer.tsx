import { Microphone, PaperPlaneRight, Paperclip, StopCircle } from '@phosphor-icons/react';
import { useRef, type FormEvent, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { useChat } from '@/features/chat/ChatContext';
import { useVoiceInput } from '@/features/chat/useVoiceInput';
import { useChatAttachment } from '@/features/chat/useChatAttachment';
import { cn } from '@/lib/cn';

export function ChatComposer() {
  const { t, i18n } = useTranslation();
  const { attachment, attachmentFormat, input, send, setAttachment, setAttachmentFormat, setInput, thinking } = useChat();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const voice = useVoiceInput(input, setInput, i18n.language);
  const attached = useChatAttachment((text, format) => {
    setAttachment(text);
    setAttachmentFormat(format);
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    send();
    if (inputRef.current) inputRef.current.style.height = '';
  };
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey) return;
    event.preventDefault();
    send();
    event.currentTarget.style.height = '';
  };

  return (
    <div className="grid shrink-0 gap-2">
      {attached.error ? (
        <p role="alert" className="text-overline text-danger">{attached.error}</p>
      ) : null}
      {attachment ? (
        <div className="grid gap-1 rounded-navigation-panel bg-canvas p-2.5 text-overline text-muted shadow-inset">
          <div className="flex items-center justify-between gap-2"><span>{t('chat.attachment.attached', { count: attachment.length })} · {attachmentFormat}</span><button type="button" onClick={() => { setAttachment(''); attached.clearError(); }} className="cursor-pointer text-link underline focus-visible:outline-2 focus-visible:outline-focus">{t('chat.attachment.remove')}</button></div>
          <p className="truncate text-ink">{attachment.slice(0, 80)}</p>
        </div>
      ) : null}
      <form onSubmit={submit} className="grid grid-cols-[auto_minmax(0,1fr)_auto_auto] gap-x-1.5 gap-y-1.5 rounded-navigation-panel bg-canvas p-2.5 shadow-inset [grid-template-areas:'input_input_input_input'_'attach_status_voice_send']">
        <input ref={attached.fileInputRef} type="file" accept={attached.accept} onChange={attached.handleFile} className="hidden" tabIndex={-1} aria-hidden />
        <textarea ref={inputRef} data-navigation-chat-input rows={1} maxLength={4000} value={input} aria-label={t('navigation.advanced.chat.inputLabel')} placeholder={t('navigation.advanced.chat.placeholder')} onKeyDown={handleKeyDown} onPaste={(event) => { attached.handlePaste(event); }} onChange={(event) => { setInput(event.target.value); event.target.style.height = 'auto'; event.target.style.height = `${Math.min(event.target.scrollHeight, 96)}px`; }} className="min-h-5.5 max-h-24 w-full resize-none overflow-y-auto border-0 bg-transparent p-0 text-navigation-strong font-semibold text-ink outline-none placeholder:text-muted [grid-area:input]" />
        <Button type="button" intent="ghost" size="navigationIcon" aria-label={t('navigation.advanced.chat.attach')} title={t('navigation.advanced.chat.attach')} onClick={attached.openPicker} className="cursor-pointer rounded-full !shadow-none hover:!shadow-none [grid-area:attach]"><Paperclip aria-hidden /></Button>
        <span role="status" className="self-center text-right text-overline text-muted [grid-area:status]">{voice.listening ? t('chat.voice.listening') : t(thinking ? 'navigation.advanced.chat.thinking' : 'navigation.advanced.chat.enterToSend')}</span>
        <Button type="button" intent="ghost" size="navigationIcon" disabled={!voice.supported || thinking} disabledReason={t('chat.voice.unsupported')} aria-pressed={voice.listening} aria-label={t(voice.listening ? 'chat.voice.stop' : 'chat.voice.start')} title={t(voice.listening ? 'chat.voice.stop' : 'chat.voice.start')} onClick={voice.toggle} className={cn('cursor-pointer rounded-full !shadow-none hover:!shadow-none [grid-area:voice]', voice.listening && 'bg-danger text-danger-text')}>
          {voice.listening ? <StopCircle aria-hidden /> : <Microphone aria-hidden />}
        </Button>
        <Button type="submit" intent="ghost" size="navigationIcon" disabled={thinking || (!input.trim() && !attachment.trim())} aria-label={t('navigation.advanced.chat.send')} title={t('navigation.advanced.chat.send')} className="cursor-pointer rounded-full !shadow-none hover:!shadow-none [grid-area:send]"><PaperPlaneRight aria-hidden /></Button>
      </form>
    </div>
  );
}
