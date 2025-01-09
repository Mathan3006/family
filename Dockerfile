
FROM python:3.8-slim
FROM node:16-alpine

# Set the working directory
WORKDIR /usr/src/app

# Copy package.json and package-lock.json
COPY package.json /usr/src/app

# Install dependencies
RUN npm install

# Copy the application files
COPY . /usr/src/app

# Expose the application port (e.g., 3000 for Node.js apps)
EXPOSE 3000

# Start the application
CMD ["npm", "start"]

