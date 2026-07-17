// ─── src/index.js ─────────────────────────────────────────
const { ApolloServer } = require('@apollo/server')
const { startStandaloneServer } = require('@apollo/server/standalone')
const { makeExecutableSchema } = require('@graphql-tools/schema')
const { WebSocketServer } = require('ws')
const { useServer } = require('graphql-ws/lib/use/ws')
const { createServer } = require('http')
const { expressMiddleware } = require('@apollo/server/express4')
const express = require('express')
const cors = require('cors')
const { PrismaClient } = require('@prisma/client')
const typeDefs = require('./schema')
const resolvers = require('./resolvers')
const { createLoaders } = require('./dataloaders')
const { authDirective } = require('./directives/auth')
const { authenticate } = require('./middleware/auth')

const prisma = new PrismaClient()

async function bootstrap() {
  const app = express()

  // 构建 Schema（含自定义 Directive）
  let schema = makeExecutableSchema({
    typeDefs,
    resolvers,
  })
  schema = authDirective(schema, 'auth')

  // Apollo Server
  const server = new ApolloServer({
    schema,
    formatError: (error) => {
      console.error('[GraphQL Error]', error)
      return {
        message: error.message,
        extensions: {
          code: error.extensions?.code || 'INTERNAL_SERVER_ERROR',
          ...(process.env.NODE_ENV !== 'production' && { stacktrace: error.extensions?.stacktrace }),
        },
      }
    },
    plugins: [
      {
        async requestDidStart(ctx) {
          console.log(`[${ctx.request.operationName || 'query'}] ${ctx.request.query?.slice(0, 80)}...`)
          return {
            async didEncounterErrors({ errors }) {
              for (const err of errors) {
                console.error(`[GraphQL Error] ${err.path?.join('.')}: ${err.message}`)
              }
            },
          }
        },
      },
    ],
  })

  // HTTP Server
  const httpServer = createServer(app)

  // WebSocket (Subscription)
  const wsServer = new WebSocketServer({
    server: httpServer,
    path: '/graphql',
  })
  useServer(
    {
      schema,
      context: async (ctx) => {
        const token = ctx.connectionParams?.authToken
        const user = token ? await authenticate(token) : null
        return { prisma, user, loaders: createLoaders(prisma) }
      },
    },
    wsServer
  )

  await server.start()

  app.use(
    '/graphql',
    cors(),
    express.json({ limit: '5mb' }),
    expressMiddleware(server, {
      context: async ({ req }) => {
        const token = req.headers.authorization?.replace('Bearer ', '')
        const user = token ? await authenticate(token) : null
        return { prisma, user, loaders: createLoaders(prisma) }
      },
    })
  )

  // Health check
  app.get('/health', (_req, res) => res.json({ status: 'ok' }))

  httpServer.listen(4000, () => {
    console.log('🚀 GraphQL Server ready at http://localhost:4000/graphql')
    console.log('🔄 Subscriptions ready at ws://localhost:4000/graphql')
  })
}

bootstrap().catch(console.error)
