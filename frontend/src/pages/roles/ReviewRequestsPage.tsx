import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Shield, CheckCircle, X, User, Calendar } from 'lucide-react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';

interface DoctorRequest {
  id: string;
  user: {
    name: string;
    email: string;
    dateOfBirth: string;
    currentRole: string;
    experience: string;
    specialization: string;
  };
  status: 'pending' | 'approved' | 'rejected';
  submittedAt: string;
  documents: {
    id: string;
    name: string;
    type: string;
  }[];
  notes?: string;
}

const ReviewRequestsPage = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRequest, setSelectedRequest] = useState<DoctorRequest | null>(null);
  const [reviewNote, setReviewNote] = useState('');

  // Mock data
  const requests: DoctorRequest[] = [
    {
      id: '1',
      user: {
        name: 'Dr. Maria Johnson',
        email: 'maria.johnson@example.com',
        dateOfBirth: '1985-06-15',
        currentRole: 'patient',
        experience: '10 years',
        specialization: 'Cardiology',
      },
      status: 'pending',
      submittedAt: '2023-03-15T09:00:00Z',
      documents: [
        { id: 'd1', name: 'Medical License', type: 'PDF' },
        { id: 'd2', name: 'Board Certification', type: 'PDF' },
      ],
    },
    {
      id: '2',
      user: {
        name: 'Dr. James Wilson',
        email: 'james.wilson@example.com',
        dateOfBirth: '1982-03-22',
        currentRole: 'patient',
        experience: '15 years',
        specialization: 'Neurology',
      },
      status: 'pending',
      submittedAt: '2023-03-14T14:30:00Z',
      documents: [
        { id: 'd3', name: 'Medical License', type: 'PDF' },
        { id: 'd4', name: 'Residency Certificate', type: 'PDF' },
      ],
    },
  ];

  const handleApprove = (request: DoctorRequest) => {
    // Handle approval logic
    alert(`Approved request for ${request.user.name}`);
  };

  const handleReject = (request: DoctorRequest) => {
    // Handle rejection logic
    alert(`Rejected request for ${request.user.name}`);
  };

  return (
    <div>
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-8"
      >
        <h1 className="text-2xl font-bold text-gray-900">Review Doctor Requests</h1>
        <p className="mt-1 text-gray-500">
          Review and verify doctor role requests from medical professionals
        </p>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2, duration: 0.5 }}
          className="lg:col-span-2"
        >
          <Card>
            <div className="mb-6">
              <Input
                placeholder="Search requests..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            <div className="space-y-4">
              {requests.map((request) => (
                <div
                  key={request.id}
                  className={`p-4 border rounded-lg transition-colors duration-200 ${
                    selectedRequest?.id === request.id
                      ? 'border-primary-500 bg-primary-50'
                      : 'border-gray-200 hover:border-primary-200 hover:bg-gray-50'
                  }`}
                  onClick={() => setSelectedRequest(request)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center">
                      <div className="h-10 w-10 rounded-full bg-primary-100 flex items-center justify-center text-primary-700 font-medium">
                        {request.user.name.split(' ').map(n => n[0]).join('')}
                      </div>
                      <div className="ml-3">
                        <h3 className="text-sm font-medium text-gray-900">
                          {request.user.name}
                        </h3>
                        <p className="text-sm text-gray-500">
                          {request.user.specialization}
                        </p>
                      </div>
                    </div>
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-warning-100 text-warning-800">
                      Pending Review
                    </span>
                  </div>

                  <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-gray-500">Experience</p>
                      <p className="font-medium">{request.user.experience}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Submitted</p>
                      <p className="font-medium">
                        {new Date(request.submittedAt).toLocaleDateString()}
                      </p>
                    </div>
                  </div>

                  <div className="mt-4">
                    <p className="text-sm text-gray-500 mb-2">Documents:</p>
                    <div className="flex flex-wrap gap-2">
                      {request.documents.map((doc) => (
                        <span
                          key={doc.id}
                          className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800"
                        >
                          {doc.name}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.4, duration: 0.5 }}
        >
          {selectedRequest ? (
            <Card>
              <div className="mb-6">
                <h3 className="text-lg font-medium text-gray-900">Request Details</h3>
                <p className="text-sm text-gray-500">
                  Review the details and make your decision
                </p>
              </div>

              <div className="space-y-6">
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Personal Information</h4>
                  <div className="space-y-2">
                    <div className="flex items-center">
                      <User className="h-4 w-4 text-gray-400 mr-2" />
                      <span className="text-sm">{selectedRequest.user.name}</span>
                    </div>
                    <div className="flex items-center">
                      <Mail className="h-4 w-4 text-gray-400 mr-2" />
                      <span className="text-sm">{selectedRequest.user.email}</span>
                    </div>
                    <div className="flex items-center">
                      <Calendar className="h-4 w-4 text-gray-400 mr-2" />
                      <span className="text-sm">
                        {new Date(selectedRequest.user.dateOfBirth).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Review Notes</h4>
                  <textarea
                    value={reviewNote}
                    onChange={(e) => setReviewNote(e.target.value)}
                    className="w-full h-24 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    placeholder="Add your review notes..."
                  />
                </div>

                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => handleReject(selectedRequest)}
                    icon={<X className="h-4 w-4" />}
                    className="flex-1"
                  >
                    Reject
                  </Button>
                  <Button
                    variant="primary"
                    onClick={() => handleApprove(selectedRequest)}
                    icon={<CheckCircle className="h-4 w-4" />}
                    className="flex-1"
                  >
                    Approve
                  </Button>
                </div>
              </div>
            </Card>
          ) : (
            <div className="h-full flex items-center justify-center text-center p-6 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
              <div>
                <Shield className="h-12 w-12 text-gray-400 mx-auto mb-3" />
                <p className="text-gray-500">
                  Select a request to review its details
                </p>
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
};

export default ReviewRequestsPage;
