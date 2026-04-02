// supabase/functions/provision-agent/index.ts
// Supabase Edge Function: stores keys in Vault, sends HMAC-signed webhook to VPS
//
// Required env vars (set via `supabase secrets set`):
//   SUPABASE_URL              — injected automatically by Supabase
//   SUPABASE_SERVICE_ROLE_KEY — injected automatically by Supabase
//   VPS_WEBHOOK_URL           — e.g. https://vps.focuscall.ai/provision
//   WEBHOOK_SECRET            — 32-byte hex string (openssl rand -hex 32)

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

interface ProvisionRequest {
  user_id: string;
  agent_id: string;
  llm_key: string;
  bot_token: string;
  llm_provider: string;
}

interface VaultEntry {
  id: string;
}

async function hmacSign(secret: string, message: string): Promise<string> {
  const encoder = new TextEncoder();
  const keyData = encoder.encode(secret);
  const msgData = encoder.encode(message);

  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    keyData,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );

  const signature = await crypto.subtle.sign("HMAC", cryptoKey, msgData);
  return Array.from(new Uint8Array(signature))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

serve(async (req: Request): Promise<Response> => {
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { "Content-Type": "application/json" },
    });
  }

  // ── Parse and validate request body ────────────────────────────────────────
  let body: ProvisionRequest;
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const { user_id, agent_id, llm_key, bot_token, llm_provider } = body;

  if (!user_id || !agent_id || !llm_key || !bot_token || !llm_provider) {
    return new Response(
      JSON.stringify({
        error: "Missing required fields",
        required: ["user_id", "agent_id", "llm_key", "bot_token", "llm_provider"],
      }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  // ── Validate env vars ───────────────────────────────────────────────────────
  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const vpsWebhookUrl = Deno.env.get("VPS_WEBHOOK_URL");
  const webhookSecret = Deno.env.get("WEBHOOK_SECRET");

  if (!supabaseUrl || !serviceRoleKey || !vpsWebhookUrl || !webhookSecret) {
    console.error("Missing required environment variables");
    return new Response(
      JSON.stringify({ error: "Server configuration error" }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }

  // ── Store keys in Supabase Vault (pgsodium AES-256-GCM) ────────────────────
  const supabase = createClient(supabaseUrl, serviceRoleKey);

  let llmKeyVaultId: string;
  let botTokenVaultId: string;

  try {
    // Store LLM API key in Vault
    const { data: llmVaultData, error: llmVaultError } = await supabase.rpc(
      "vault_create_secret",
      {
        secret: llm_key,
        name: `llm_key_${user_id}_${agent_id}`,
        description: `LLM API key for user ${user_id} agent ${agent_id}`,
      },
    );

    if (llmVaultError) {
      throw new Error(`Vault error (llm_key): ${llmVaultError.message}`);
    }

    llmKeyVaultId = (llmVaultData as VaultEntry).id;

    // Store bot token in Vault
    const { data: botVaultData, error: botVaultError } = await supabase.rpc(
      "vault_create_secret",
      {
        secret: bot_token,
        name: `bot_token_${user_id}_${agent_id}`,
        description: `Telegram bot token for user ${user_id} agent ${agent_id}`,
      },
    );

    if (botVaultError) {
      throw new Error(`Vault error (bot_token): ${botVaultError.message}`);
    }

    botTokenVaultId = (botVaultData as VaultEntry).id;
  } catch (err) {
    console.error("Vault storage failed:", err);
    return new Response(
      JSON.stringify({
        error: "Failed to store credentials in Vault",
        detail: err instanceof Error ? err.message : String(err),
      }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }

  console.log(
    `Vault storage OK: llm_key_vault_id=${llmKeyVaultId} bot_token_vault_id=${botTokenVaultId}`,
  );

  // ── Build HMAC-signed webhook payload ──────────────────────────────────────
  // Timestamp in Unix seconds (used for replay protection on receiver side)
  const timestamp = Math.floor(Date.now() / 1000).toString();

  // Sign: user_id + agent_id + timestamp (metadata only — not the keys)
  const signatureMessage = `${user_id}:${agent_id}:${timestamp}`;
  let signature: string;

  try {
    signature = await hmacSign(webhookSecret, signatureMessage);
  } catch (err) {
    console.error("HMAC signing failed:", err);
    return new Response(
      JSON.stringify({ error: "Signature generation failed" }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }

  // ── Send webhook to VPS ────────────────────────────────────────────────────
  // Keys are included in the payload: secured by HTTPS + HMAC + timestamp.
  // On the VPS they are passed directly to Docker ENV — never written to disk.
  const webhookPayload = {
    user_id,
    agent_id,
    llm_key,       // Plain-text for Docker ENV (secured in transit by HTTPS+HMAC)
    bot_token,     // Plain-text for Docker ENV (secured in transit by HTTPS+HMAC)
    llm_provider,
    llm_key_vault_id: llmKeyVaultId,
    bot_token_vault_id: botTokenVaultId,
  };

  let webhookResponse: Response;
  try {
    webhookResponse = await fetch(`${vpsWebhookUrl}/provision`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Timestamp": timestamp,
        "X-Signature": signature,
      },
      body: JSON.stringify(webhookPayload),
    });
  } catch (err) {
    console.error("Webhook delivery failed:", err);
    return new Response(
      JSON.stringify({
        error: "Failed to reach VPS webhook",
        detail: err instanceof Error ? err.message : String(err),
      }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }

  if (!webhookResponse.ok) {
    const responseText = await webhookResponse.text();
    console.error(`VPS webhook returned ${webhookResponse.status}: ${responseText}`);
    return new Response(
      JSON.stringify({
        error: "VPS webhook rejected the request",
        status: webhookResponse.status,
        detail: responseText,
      }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    );
  }

  const webhookResult = await webhookResponse.json();
  console.log(`Provisioning initiated for user=${user_id} agent=${agent_id}:`, webhookResult);

  return new Response(
    JSON.stringify({
      ok: true,
      status: "provisioning",
      user_id,
      agent_id,
      llm_key_vault_id: llmKeyVaultId,
      bot_token_vault_id: botTokenVaultId,
    }),
    { status: 202, headers: { "Content-Type": "application/json" } },
  );
});
