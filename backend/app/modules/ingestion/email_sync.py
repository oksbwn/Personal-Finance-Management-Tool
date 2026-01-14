import imaplib
import email
from email.header import decode_header
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.app.modules.ingestion.registry import EmailParserRegistry
from backend.app.modules.ingestion.services import IngestionService

class EmailSyncService:
    @staticmethod
    def sync_emails(
        db: Session, 
        tenant_id: str, 
        config_id: str, # Accept ID directly
        imap_server: str, 
        email_user: str, 
        email_pass: str,
        folder: str = "INBOX",
        search_criterion: str = 'UNSEEN',
        since_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Connect to IMAP, fetch unread emails, parse them, and ingest transactions.
        """
        from backend.app.modules.ingestion import models as ingestion_models
        from datetime import datetime
        
        # Create Log Entry
        log_entry = ingestion_models.EmailSyncLog(
            config_id=config_id,
            tenant_id=tenant_id,
            status="running",
            message="Starting sync..."
        )
        db.add(log_entry)
        db.commit() # Commit to get ID
        db.refresh(log_entry)

        stats = {"total_fetched": 0, "processed": 0, "failed": 0, "errors": []}
        
        try:
            # Connect to the server
            mail = imaplib.IMAP4_SSL(imap_server)
            mail.login(email_user, email_pass)
            mail.select(folder)

            # Search for emails
            final_criterion = search_criterion
            if since_date:
                # IMAP SINCE format: DD-Mon-YYYY
                date_str = since_date.strftime("%d-%b-%Y")
                if search_criterion == 'ALL':
                    final_criterion = f'SINCE "{date_str}"'
                else:
                    final_criterion = f'({search_criterion} SINCE "{date_str}")'
            
            print(f"[EmailSync] Searching with: {final_criterion}")
            status, messages = mail.search(None, final_criterion)
            if status != "OK":
                print(f"[EmailSync] Search failed: {status}")
                return {"status": "error", "message": f"Search failed: {status}"}

            email_ids = messages[0].split()
            print(f"[EmailSync] Found {len(email_ids)} emails.")
            stats["total_fetched"] = len(email_ids)

            for e_id in email_ids:
                try:
                    # Fetch the email message by ID
                    status, msg_data = mail.fetch(e_id, "(RFC822)")
                    if status != "OK":
                        continue
                    
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            
                            # Decode subject
                            subject_header = msg["Subject"]
                            subject, encoding = decode_header(subject_header)[0]
                            if isinstance(subject, bytes):
                                subject = subject.decode(encoding if encoding else "utf-8")
                            
                            print(f"[EmailSync] Checking: {subject}")
                            
                            # Extract body
                            body = ""
                            html_body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    content_type = part.get_content_type()
                                    content_disposition = str(part.get("Content-Disposition"))
                                    if "attachment" in content_disposition:
                                        continue
                                    if content_type == "text/plain":
                                        payload = part.get_payload(decode=True)
                                        if payload: body = payload.decode(errors='ignore')
                                    elif content_type == "text/html":
                                        payload = part.get_payload(decode=True)
                                        if payload: html_body = payload.decode(errors='ignore')
                            else:
                                content_type = msg.get_content_type()
                                payload = msg.get_payload(decode=True)
                                if payload:
                                    content = payload.decode(errors='ignore')
                                    if content_type == "text/html":
                                        html_body = content
                                    else:
                                        body = content

                            # Fallback to HTML if plain text is empty
                            if not body.strip() and html_body.strip():
                                body = html_body

                            # Clean HTML if necessary
                            if "<html" in body.lower() or "<div" in body.lower() or "<p" in body.lower():
                                body = re.sub('<script.*?>.*?</script>', ' ', body, flags=re.DOTALL | re.IGNORECASE)
                                body = re.sub('<style.*?>.*?</style>', ' ', body, flags=re.DOTALL | re.IGNORECASE)
                                body = re.sub('<[^<]+?>', ' ', body)
                                body = " ".join(body.split())

                            # Extract Email Header Date as Fallback
                            email_date = None
                            try:
                                from email.utils import parsedate_to_datetime
                                email_date = parsedate_to_datetime(msg.get("Date"))
                            except: pass

                            # Parse via Registry
                            parsed = EmailParserRegistry.parse(subject, body, email_date)
                            if parsed:
                                print(f"[EmailSync] SUCCESS! Parsed: {parsed.amount} {parsed.recipient} (Ref: {parsed.ref_id})")
                                result = IngestionService.process_transaction(db, tenant_id, parsed)
                                status = result.get("status")
                                
                                if status in ["success", "triaged"]:
                                    stats["processed"] += 1
                                    print(f"[EmailSync] {status.upper()}: {parsed.amount} to {result.get('account', 'Unknown')}")
                                elif result.get("deduplicated"):
                                    # Explicitly log deduplication for user confidence
                                    print(f"[EmailSync] SKIPPED (Duplicate: {result.get('reason')})")
                                else:
                                    stats["failed"] += 1
                                    reason = result.get('message') or result.get('reason') or "Unknown Error"
                                    err_msg = f"Ingestion failed for '{subject[:30]}...': {reason}"
                                    stats["errors"].append(err_msg)
                                    print(f"[EmailSync] {err_msg}")
                            else:
                                stats["failed"] += 1
                                # Log why it was skipped (now without cap for terminal debugging)
                                err_msg = f"No parser matched for: {subject[:40]}..."
                                stats["errors"].append(err_msg)
                                # Print body snippet for debugging
                                if any(k in (subject + " " + body).lower() for k in ["txn", "upi", "hdfc", "spent", "debited"]):
                                    clean_body = body.replace("\n", " ").strip()
                                    print(f"[EmailSync] Debug Body Snippet: {clean_body[:300]}...")

                except Exception as e:
                    stats["errors"].append(f"Error processing message {e_id}: {str(e)}")
                    stats["failed"] += 1

            mail.close()
            mail.logout()

            # Update Log Success
            if log_entry:
                log_entry.status = "completed"
                log_entry.completed_at = datetime.utcnow()
                log_entry.items_processed = stats["processed"]
                log_entry.message = f"Found {stats['total_fetched']}, Processed {stats['processed']}"
                if stats["errors"]:
                    # Join first 3 errors for the summary message
                    error_summary = "; ".join(stats["errors"][:3])
                    log_entry.message += f" (Errors: {error_summary})"
                db.commit()

            return {
                "status": "completed",
                "stats": stats
            }

        except Exception as e:
            # Update Log Error
            if log_entry:
                log_entry.status = "error"
                log_entry.completed_at = datetime.utcnow()
                log_entry.message = str(e)
                db.commit()

            return {"status": "error", "message": f"Connection failed: {str(e)}", "stats": stats}
