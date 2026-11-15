"use client";

import { useParams } from "next/navigation";
import { Suspense } from "react";
import { ChatScreen } from "@/components/chat/chat-screen";
import { Loading } from "@/components/states/states";

// Saved conversation (S33 rule 7).
export default function ConversationPage() {
  const { conversationId } = useParams<{ conversationId: string }>();
  return (
    <Suspense fallback={<Loading label="Loading chat…" rows={2} />}>
      <ChatScreen key={conversationId} conversationId={conversationId} />
    </Suspense>
  );
}
