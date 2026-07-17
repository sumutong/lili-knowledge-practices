// ─── src/stripe-client.js ─────────────────────────────────
const Stripe = require('stripe')

class StripeClient {
  constructor(config = {}) {
    this.stripe = new Stripe(config.secretKey || process.env.STRIPE_SECRET_KEY, {
      apiVersion: '2025-01-27.acacia',
      maxNetworkRetries: 3,
      timeout: 30000,
    })
    this.webhookSecret = config.webhookSecret || process.env.STRIPE_WEBHOOK_SECRET
    this.defaultCurrency = config.defaultCurrency || 'cny'
    this.successUrl = config.successUrl || 'https://example.com/payment/success'
    this.cancelUrl = config.cancelUrl || 'https://example.com/payment/cancel'
  }

  /** ─── 支付会话 ──────────────────────────────────── */

  /**
   * 创建 Checkout Session（Stripe 托管支付页）
   */
  async createCheckoutSession(options) {
    const {
      customerEmail,
      customerId,
      lineItems,
      metadata,
      mode = 'payment', // 'payment' | 'subscription' | 'setup'
      successUrl = this.successUrl,
      cancelUrl = this.cancelUrl,
      discounts = [],
      shippingAddressCollection = false,
      locale = 'zh',
    } = options

    const sessionConfig = {
      mode,
      success_url: `${successUrl}?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: cancelUrl,
      line_items: lineItems.map(item => ({
        price_data: item.price_data ? {
          currency: item.price_data.currency || this.defaultCurrency,
          product_data: {
            name: item.price_data.name,
            description: item.price_data.description,
            images: item.price_data.images || [],
            metadata: item.price_data.metadata,
          },
          unit_amount: Math.round(parseFloat(item.price_data.amount) * 100), // 转为分
          ...(item.price_data.recurring && { recurring: item.price_data.recurring }),
        } : undefined,
        price: item.price || undefined,
        quantity: item.quantity || 1,
        adjustable_quantity: item.adjustable_quantity,
      })),
      metadata: {
        ...metadata,
        source: 'api',
        environment: process.env.NODE_ENV || 'development',
      },
      locale,
      shipping_address_collection: shippingAddressCollection
        ? { allowed_countries: ['CN', 'US', 'JP', 'HK'] }
        : undefined,
      discounts: discounts.map(d => ({
        coupon: d.coupon,
        promotion_code: d.promotionCode,
      })),
      customer_email: customerEmail,
      ...(customerId && { customer: customerId }),
      allow_promotion_codes: true,
      billing_address_collection: 'auto',
      payment_method_types: ['card', 'alipay', 'wechat_pay'],
      // 自动创建客户
      customer_creation: !customerId ? 'always' : undefined,
    }

    const session = await this.stripe.checkout.sessions.create(sessionConfig)
    return { id: session.id, url: session.url }
  }

  /** ─── Payment Intent (自定义支付流) ──────────────── */

  /**
   * 创建 Payment Intent
   */
  async createPaymentIntent(options) {
    const {
      amount,
      currency = this.defaultCurrency,
      customerId,
      paymentMethodId,
      metadata,
      captureMethod = 'automatic', // 'automatic' | 'manual'
      description,
      statementDescriptor,
      idempotencyKey,
      setupFutureUsage, // 'on_session' | 'off_session'
    } = options

    const params = {
      amount: Math.round(parseFloat(amount) * 100),
      currency,
      capture_method: captureMethod,
      metadata,
      description,
      statement_descriptor: statementDescriptor?.slice(0, 22),
      ...(customerId && { customer: customerId }),
      ...(paymentMethodId && { payment_method: paymentMethodId }),
      ...(setupFutureUsage && { setup_future_usage: setupFutureUsage }),
      automatic_payment_methods: { enabled: true },
    }

    const intent = idempotencyKey
      ? await this.stripe.paymentIntents.create(params, { idempotencyKey })
      : await this.stripe.paymentIntents.create(params)

    return {
      id: intent.id,
      clientSecret: intent.client_secret,
      status: intent.status,
      amount: intent.amount,
      currency: intent.currency,
    }
  }

  /**
   * 确认 Payment Intent
   */
  async confirmPaymentIntent(intentId, options = {}) {
    const intent = await this.stripe.paymentIntents.confirm(intentId, {
      payment_method: options.paymentMethodId,
      return_url: options.returnUrl,
      receipt_email: options.receiptEmail,
    })
    return intent
  }

  /**
   * 获取 Payment Intent 详情
   */
  async retrievePaymentIntent(intentId) {
    return this.stripe.paymentIntents.retrieve(intentId)
  }

  /**
   * 退款
   */
  async refund(paymentIntentId, options = {}) {
    const { amount, reason, metadata, idempotencyKey } = options

    const params = {
      payment_intent: paymentIntentId,
      reason: reason || 'requested_by_customer', // 'duplicate' | 'fraudulent' | 'requested_by_customer'
      metadata,
      ...(amount && { amount: Math.round(parseFloat(amount) * 100) }),
    }

    const refund = idempotencyKey
      ? await this.stripe.refunds.create(params, { idempotencyKey })
      : await this.stripe.refunds.create(params)

    return {
      id: refund.id,
      status: refund.status,
      amount: refund.amount,
      currency: refund.currency,
    }
  }

  /** ─── 客户管理 ──────────────────────────────────── */

  /**
   * 创建客户
   */
  async createCustomer(options) {
    const { email, name, metadata, paymentMethodId, address } = options

    const customer = await this.stripe.customers.create({
      email,
      name,
      metadata,
      ...(paymentMethodId && { payment_method: paymentMethodId, invoice_settings: { default_payment_method: paymentMethodId } }),
      ...(address && { address }),
    })

    return {
      id: customer.id,
      email: customer.email,
      name: customer.name,
    }
  }

  /**
   * 获取客户支付方式
   */
  async listPaymentMethods(customerId, type = 'card') {
    const methods = await this.stripe.paymentMethods.list({
      customer: customerId,
      type,
    })
    return methods.data.map(m => ({
      id: m.id,
      brand: m.card?.brand,
      last4: m.card?.last4,
      expMonth: m.card?.exp_month,
      expYear: m.card?.exp_year,
      isDefault: m.metadata?.default === 'true',
    }))
  }

  /** ─── 订阅管理 ──────────────────────────────────── */

  /**
   * 创建订阅
   */
  async createSubscription(options) {
    const {
      customerId,
      priceId,
      trialDays,
      metadata,
      couponId,
      paymentBehavior = 'default_incomplete',
      billingCycleAnchor,
    } = options

    const subscription = await this.stripe.subscriptions.create({
      customer: customerId,
      items: [{ price: priceId }],
      trial_period_days: trialDays,
      metadata,
      ...(couponId && { coupon: couponId }),
      payment_behavior: paymentBehavior,
      ...(billingCycleAnchor && { billing_cycle_anchor: billingCycleAnchor }),
      expand: ['latest_invoice.payment_intent'],
    })

    return {
      id: subscription.id,
      status: subscription.status,
      currentPeriodStart: subscription.current_period_start,
      currentPeriodEnd: subscription.current_period_end,
      clientSecret: subscription.latest_invoice?.payment_intent?.client_secret,
    }
  }

  /**
   * 取消订阅
   */
  async cancelSubscription(subscriptionId, atPeriodEnd = true) {
    const subscription = atPeriodEnd
      ? await this.stripe.subscriptions.update(subscriptionId, {
          cancel_at_period_end: true,
        })
      : await this.stripe.subscriptions.cancel(subscriptionId)

    return {
      id: subscription.id,
      status: subscription.status,
      cancelAt: subscription.cancel_at,
    }
  }

  /**
   * 重新激活订阅
   */
  async reactivateSubscription(subscriptionId) {
    const subscription = await this.stripe.subscriptions.update(subscriptionId, {
      cancel_at_period_end: false,
    })
    return subscription
  }

  /** ─── Webhook 处理 ──────────────────────────────── */

  /**
   * 验证并解析 Webhook
   */
  constructWebhookEvent(payload, signature) {
    if (!this.webhookSecret) throw new Error('Webhook secret not configured')

    return this.stripe.webhooks.constructEvent(
      payload,
      signature,
      this.webhookSecret
    )
  }

  /**
   * Webhook 事件处理器
   */
  async handleWebhookEvent(event) {
    console.log(`📨 Stripe webhook: ${event.type}`)

    switch (event.type) {
      case 'checkout.session.completed': {
        const session = event.data.object
        await this.handleCheckoutCompleted(session)
        break
      }

      case 'payment_intent.succeeded': {
        const intent = event.data.object
        await this.handlePaymentSucceeded(intent)
        break
      }

      case 'payment_intent.payment_failed': {
        const intent = event.data.object
        await this.handlePaymentFailed(intent)
        break
      }

      case 'invoice.paid': {
        const invoice = event.data.object
        await this.handleInvoicePaid(invoice)
        break
      }

      case 'invoice.payment_failed': {
        const invoice = event.data.object
        await this.handleInvoiceFailed(invoice)
        break
      }

      case 'customer.subscription.created': {
        const subscription = event.data.object
        await this.handleSubscriptionCreated(subscription)
        break
      }

      case 'customer.subscription.deleted': {
        const subscription = event.data.object
        await this.handleSubscriptionDeleted(subscription)
        break
      }

      case 'customer.subscription.updated': {
        const subscription = event.data.object
        await this.handleSubscriptionUpdated(subscription)
        break
      }

      case 'charge.refunded': {
        const charge = event.data.object
        await this.handleRefund(charge)
        break
      }

      case 'charge.dispute.created': {
        const dispute = event.data.object
        await this.handleDispute(dispute)
        break
      }

      default: {
        console.log(`Unhandled event: ${event.type}`)
      }
    }
  }

  // ─── 事件处理回调（由应用层实现） ────────────────

  async handleCheckoutCompleted(session) {
    // 更新订单状态
    const { metadata, customer_email, customer, amount_total, payment_status } = session
    console.log(`✅ Checkout completed: ${session.id}, amount: ${amount_total}`)

    // 触发订单完成流程
    // await orderService.completeOrder(metadata.orderId, {
    //   stripeSessionId: session.id,
    //   amount: amount_total,
    //   customerEmail: customer_email,
    //   stripeCustomerId: customer,
    // })
  }

  async handlePaymentSucceeded(intent) {
    const { metadata } = intent
    console.log(`💰 Payment succeeded: ${intent.id}, amount: ${intent.amount}`)
    // 更新订单状态为已支付
    // 发放权益
  }

  async handlePaymentFailed(intent) {
    const { metadata, last_payment_error } = intent
    console.log(`❌ Payment failed: ${intent.id}`, last_payment_error?.message)
    // 通知用户支付失败
    // 记录失败原因
  }

  async handleInvoicePaid(invoice) {
    console.log(`📃 Invoice paid: ${invoice.id}`)
  }

  async handleInvoiceFailed(invoice) {
    console.log(`❌ Invoice failed: ${invoice.id}`)
    // 暂停订阅服务
  }

  async handleSubscriptionCreated(subscription) {
    console.log(`🔄 Subscription created: ${subscription.id}`)
  }

  async handleSubscriptionDeleted(subscription) {
    console.log(`🔄 Subscription deleted: ${subscription.id}`)
    // 降级用户服务
  }

  async handleSubscriptionUpdated(subscription) {
    console.log(`🔄 Subscription updated: ${subscription.id}`)
  }

  async handleRefund(charge) {
    console.log(`↩️ Refund: ${charge.id}, amount: ${charge.amount_refunded}`)
    // 更新退款状态
  }

  async handleDispute(dispute) {
    console.log(`⚠️ Dispute: ${dispute.id}, reason: ${dispute.reason}`)
    // 处理争议
  }
}

module.exports = { StripeClient }
