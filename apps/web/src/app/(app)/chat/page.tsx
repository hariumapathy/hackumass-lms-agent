import { Suspense } from "react";
import { ChatScreen } from "@/components/chat/chat-screen";
import { Loading } from "@/components/states/states";

// New conversation (S33). Suspense: ChatScreen reads ?prefill= from the URL.
export default function ChatPage() {
  return (
    <Suspense fallback={<Loading label="Loading chat…" rows={2} />}>
      <ChatScreen />
    </Suspense>
  );
}
