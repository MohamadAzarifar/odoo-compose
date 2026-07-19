/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ImageField, imageField } from "@web/views/fields/image/image_field";
import { onWillStart, useState } from "@odoo/owl";

/**
 * Fingerprint image field with an optional in-browser SecuGen WebAPI capture.
 *
 * The SecuGen scanner is reached through the SGIBioSrv WebAPI service running
 * on the operator's PC (default https://localhost:8443/SGIFPCapture). This
 * widget is intentionally NON-BLOCKING: if the device or its service is not
 * configured or not reachable, the operator can still upload an image
 * manually through the standard image control. A missing biometric device must
 * never hold up a booking or a transfer.
 */
export class SaFingerprintField extends ImageField {
    static template = "sa_property_management.SaFingerprintField";

    setup() {
        super.setup();
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.captureState = useState({ scanning: false, available: false });

        onWillStart(async () => {
            try {
                this.secugenConfig = await this.orm.call(
                    "sa.biometric.verification", "get_secugen_config", []
                );
                this.captureState.available = !!(
                    this.secugenConfig && this.secugenConfig.url
                );
            } catch {
                // No configuration accessor / no access: just hide the button.
                this.secugenConfig = null;
                this.captureState.available = false;
            }
        });
    }

    /**
     * Trigger a live fingerprint capture via the local SecuGen WebAPI.
     * Any failure (service down, certificate not trusted, no finger, bad
     * quality) is reported as a soft notification — never an exception — so the
     * transaction flow continues and the operator can upload manually.
     */
    async onScanFingerprint() {
        if (this.captureState.scanning) {
            return;
        }
        const cfg = this.secugenConfig || {};
        const url = cfg.url;
        if (!url) {
            this.notification.add(
                _t("No fingerprint device is configured. Upload an image instead."),
                { type: "warning" }
            );
            return;
        }

        this.captureState.scanning = true;
        try {
            const body = new URLSearchParams();
            body.append("Licstr", cfg.license || "");
            body.append("Quality", String(cfg.quality ?? 50));
            body.append("Timeout", String(cfg.timeout ?? 10000));
            // 0 = no template, return the raw image only.
            body.append("TemplateFormat", "ISO");
            body.append("ImageWSQRate", "0.75");

            const controller = new AbortController();
            const timer = setTimeout(
                () => controller.abort(),
                (cfg.timeout ?? 10000) + 5000
            );
            let response;
            try {
                response = await fetch(url, {
                    method: "POST",
                    body,
                    signal: controller.signal,
                });
            } finally {
                clearTimeout(timer);
            }

            const data = await response.json();
            // SecuGen WebAPI: ErrorCode 0 = success; BMPBase64 holds the image.
            if (Number(data.ErrorCode) !== 0 || !data.BMPBase64) {
                this.notification.add(
                    _t(
                        "Fingerprint capture failed (code %s). Re-scan or upload an image instead.",
                        data.ErrorCode ?? "?"
                    ),
                    { type: "warning" }
                );
                return;
            }

            const quality = Number(data.ImageQuality ?? 0);
            const minQuality = cfg.quality ?? 50;
            if (quality && quality < minQuality) {
                this.notification.add(
                    _t(
                        "Low fingerprint quality (%s/%s). You can keep it or re-scan.",
                        quality,
                        minQuality
                    ),
                    { type: "warning" }
                );
            }

            // The WebAPI returns a base64 BMP; store it directly on the field.
            await this.props.record.update({
                [this.props.name]: data.BMPBase64,
            });
            this.notification.add(_t("Fingerprint captured."), {
                type: "success",
            });
        } catch (error) {
            // Service unreachable / CORS / cert not trusted / aborted.
            this.notification.add(
                _t(
                    "Could not reach the SecuGen service. Confirm the WebAPI is running and its certificate is trusted, or upload an image instead."
                ),
                { type: "warning", sticky: false }
            );
            // Swallow: never block the flow on a device problem.
            console.warn("SecuGen capture error:", error);
        } finally {
            this.captureState.scanning = false;
        }
    }
}

export const saFingerprintField = {
    ...imageField,
    component: SaFingerprintField,
    displayName: _t("Fingerprint Capture"),
};

registry.category("fields").add("sa_fingerprint", saFingerprintField);
